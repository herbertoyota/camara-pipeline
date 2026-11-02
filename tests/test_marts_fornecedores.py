"""Testes dos marts de fornecedores (pergunta 2). Dados inventados, DuckDB em memória.

Fornecedores de 2024 (valor líquido), conferidos à mão:
- ALFA (CNPJ 11111111000111): 500 + 300 = 800
- BETA (CNPJ 22222222000122): 800 (empate com ALFA; ALFA vem primeiro pelo documento)
- PF (CPF, hash abcdef01...): 600, nome PESSOA FISICA
- GAMA (CNPJ 33333333000133): 100 + (-20) = 80 (saldo com estorno)
- OCULTO (CNPJ 44444444000144): 50, nome NOME OCULTADO
- 8 CNPJs pequenos (55555555000055 a 55555555000062): 10 cada (empate na fronteira do top 10)
Total de 2024 = 800 + 800 + 600 + 80 + 50 + 80 = 2.410. Fornecedores = 13.
"""

import hashlib

import duckdb
import pytest

from src.marts import construir_marts

HASH_PF = hashlib.sha256(b"sal-teste|44444444444").hexdigest()


def linha(**campos):
    base = {"ano_arquivo": 2024, "mes": 1, "id_deputado": 1, "eh_lideranca": False,
            "sigla_partido": "AAA", "sigla_uf": "SP", "documento_fornecedor": "",
            "tipo_documento_fornecedor": "CNPJ", "fornecedor_nome": "", "tipo_despesa": "TELEFONIA", "valor_documento": 0,
            "valor_glosa": 0, "valor_liquido": 0, "liquido_diverge": False}
    base.update(campos)
    return base


def inserir(con, linhas):
    for l in linhas:
        colunas = ", ".join(l)
        marcas = ", ".join("?" for _ in l)
        con.execute(f"INSERT INTO refined.despesas_deputado ({colunas}) VALUES ({marcas})", list(l.values()))


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("""CREATE TABLE refined.despesas_deputado (
        ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
        sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
        tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, tipo_despesa VARCHAR, valor_documento DECIMAL(18,2),
        valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2), liquido_diverge BOOLEAN)""")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1, 'Dep Um')")
    inserir(c, [
        linha(documento_fornecedor="11111111000111", fornecedor_nome="ALFA LTDA", valor_documento=500, valor_glosa=0, valor_liquido=500),
        linha(documento_fornecedor="11111111000111", fornecedor_nome="ALFA LTDA", mes=2, valor_documento=300, valor_glosa=0, valor_liquido=300),
        linha(documento_fornecedor="22222222000122", fornecedor_nome="BETA SA", valor_documento=800, valor_glosa=0, valor_liquido=800),
        linha(documento_fornecedor=HASH_PF, tipo_documento_fornecedor="CPF", fornecedor_nome="PESSOA FISICA",
              valor_documento=600, valor_glosa=0, valor_liquido=600),
        linha(documento_fornecedor="33333333000133", fornecedor_nome="GAMA", valor_documento=100, valor_glosa=0, valor_liquido=100),
        linha(documento_fornecedor="33333333000133", fornecedor_nome="GAMA", mes=2, valor_documento=-20, valor_glosa=0, valor_liquido=-20),
        linha(documento_fornecedor="44444444000144", fornecedor_nome="NOME OCULTADO", valor_documento=50, valor_glosa=0, valor_liquido=50),
    ] + [
        linha(documento_fornecedor=f"5555555500{n:04d}"[:14], fornecedor_nome=f"PEQUENO {n}", valor_documento=10, valor_glosa=0, valor_liquido=10)
        for n in range(55, 63)
    ])
    construir_marts(c)
    yield c
    c.close()


def top(con, periodo):
    return con.execute(
        "SELECT posicao, identificador, fornecedor_nome, valor_liquido_total, participacao_pct "
        "FROM marts.top_fornecedores WHERE periodo = ? ORDER BY posicao", [periodo]
    ).fetchall()


# --- top 10 ---------------------------------------------------------------

def test_top10_tem_dez_linhas_por_periodo(con):
    for periodo in ("2024", "TOTAL"):
        assert len(top(con, periodo)) == 10


def test_empate_no_valor_desfeito_pelo_documento(con):
    rows = top(con, "2024")
    assert rows[0][1] == "11111111000111"  # ALFA e BETA empatam em 800; ALFA vem primeiro
    assert rows[1][1] == "22222222000122"


def test_empate_na_fronteira_do_top10_e_deterministico(con):
    # Posições 1 a 5: ALFA, BETA, PF, GAMA, OCULTO. Posições 6 a 13: oito PEQUENO com 10 cada.
    # Entram no top 10 os 5 primeiros pelo documento (empate na fronteira).
    rows = top(con, "2024")
    pequenos = [r[1] for r in rows if r[2].startswith("PEQUENO")]
    assert pequenos == [f"5555555500{n:04d}" for n in range(55, 60)]


def test_pessoa_fisica_aparece_so_com_prefixo_curto_do_hash(con):
    rows = top(con, "2024")
    pf = [r for r in rows if r[2] == "PESSOA FISICA"][0]
    assert pf[1] == "ID-" + HASH_PF[:8]
    assert HASH_PF not in pf[1]


def test_fornecedor_com_nome_ocultado_aparece_pelo_cnpj(con):
    rows = top(con, "2024")
    oculto = [r for r in rows if r[2] == "NOME OCULTADO"][0]
    assert oculto[1] == "44444444000144"  # CNPJ inteiro, sem nome


def test_estorno_abate_o_fornecedor(con):
    total = con.execute(
        "SELECT valor_liquido_total FROM marts.gasto_por_fornecedor WHERE identificador = '33333333000133' AND periodo = '2024'"
    ).fetchone()[0]
    assert float(total) == 80.0


def test_participacao_do_top10_soma_a_concentracao(con):
    soma_top = sum(r[4] for r in top(con, "2024"))
    part = con.execute(
        "SELECT participacao_top10_pct FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()[0]
    assert float(soma_top) == pytest.approx(float(part))


# --- concentração ---------------------------------------------------------

def test_concentracao_totais_batem_com_a_base(con):
    gasto, forn = con.execute(
        "SELECT gasto_total, fornecedores FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()
    assert float(gasto) == 2410.0
    assert forn == 13


def test_concentracao_top10_e_hhi_com_valores_conferidos(con):
    _, _, top10, part, hhi = con.execute(
        "SELECT periodo, gasto_total, valor_top10, participacao_top10_pct, hhi "
        "FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()
    # Top 10: ALFA 800, BETA 800, PF 600, GAMA 80 (100 - 20), OCULTO 50, e 5 pequenos de 10.
    assert float(top10) == pytest.approx(800 + 800 + 600 + 80 + 50 + 5 * 10)
    assert float(part) == pytest.approx(100.0 * float(top10) / 2410.0)
    # HHI sobre todos os 13 fornecedores: soma dos quadrados das participações em %.
    valores = [800, 800, 600, 80, 50] + [10] * 8
    shares = [100.0 * v / 2410.0 for v in valores]
    assert float(hhi) == pytest.approx(sum(s * s for s in shares), rel=1e-6)


def test_total_inclui_periodo_TOTAL(con):
    total = con.execute(
        "SELECT gasto_total FROM marts.concentracao_fornecedores WHERE periodo = 'TOTAL'"
    ).fetchone()[0]
    assert float(total) == 2410.0


def test_hhi_so_com_fornecedores_de_total_positivo(con):
    # Fornecedor com saldo negativo (estornos maiores que as compras): fica fora do HHI.
    inserir(con, [linha(documento_fornecedor="66666666000166", fornecedor_nome="NEGATIVO",
                        valor_documento=-40, valor_glosa=0, valor_liquido=-40)])
    construir_marts(con)
    gasto, forn, hhi, excluidos, valor_excl = con.execute(
        "SELECT gasto_total, fornecedores, hhi, fornecedores_excluidos_hhi, valor_excluido_hhi "
        "FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()
    assert float(gasto) == 2370.0 and forn == 14
    assert excluidos == 1 and float(valor_excl) == -40.0
    positivos = [800, 800, 600, 80, 50] + [10] * 8  # os 13 fornecedores com total positivo
    assert float(hhi) == pytest.approx(sum((100.0 * v / 2370.0) ** 2 for v in positivos), rel=1e-6)


def test_lancamento_interno_fica_no_total_e_sai_do_ranking(con):
    inserir(con, [linha(documento_fornecedor="00530352000159", fornecedor_nome="COMPLEMENTACAO DO AUXILIO",
                        valor_documento=1000, valor_glosa=0, valor_liquido=1000)])
    construir_marts(con)
    interno = con.execute(
        "SELECT eh_lancamento_interno, valor_liquido_total FROM marts.gasto_por_fornecedor "
        "WHERE identificador = '00530352000159' AND periodo = '2024'"
    ).fetchone()
    assert interno[0] is True and float(interno[1]) == 1000.0
    gasto, interno_val = con.execute(
        "SELECT gasto_total, valor_lancamento_interno FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()
    assert float(gasto) == 2410.0 and float(interno_val) == 1000.0  # gasto externo; interno à parte
    ids = {r[0] for r in con.execute("SELECT identificador FROM marts.top_fornecedores WHERE periodo = '2024'").fetchall()}
    assert "00530352000159" not in ids and len(ids) == 10


def test_raiz_soma_filiais_e_muda_a_posicao_do_grupo(con):
    # Filial de ALFA com 300: a raiz 11111111 vira 1100 e passa a liderar o ranking por raiz.
    inserir(con, [linha(documento_fornecedor="11111111000222", fornecedor_nome="ALFA FILIAL",
                        valor_documento=300, valor_glosa=0, valor_liquido=300)])
    construir_marts(con)
    raiz = con.execute(
        "SELECT valor_liquido_total, cnpjs FROM marts.gasto_por_raiz WHERE raiz = '11111111' AND periodo = '2024'"
    ).fetchone()
    assert float(raiz[0]) == 1100.0 and raiz[1] == 2
    top_raiz = con.execute(
        "SELECT raiz, posicao FROM marts.top_raizes WHERE periodo = '2024' AND posicao = 1"
    ).fetchone()
    assert top_raiz[0] == "11111111"
    beta = con.execute(
        "SELECT posicao, posicao_no_outro_ranking FROM marts.comparacao_top10_cnpj_raiz "
        "WHERE ranking = 'CNPJ' AND chave = '22222222000122' AND periodo = '2024'"
    ).fetchone()
    assert beta == (2, 2)  # BETA é 2º por CNPJ; a raiz 22222222 é 2ª por raiz


def test_concentracao_raiz_tem_metricas(con):
    row = con.execute(
        "SELECT participacao_top10_raiz_pct, hhi_raiz FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()
    assert row[0] is not None and row[1] is not None


def test_documento_generico_nao_se_agrupa_e_fica_marcado(con):
    inserir(con, [linha(documento_fornecedor="00000000000001", fornecedor_nome="CELULAR FUNCIONAL",
                        valor_documento=50, valor_glosa=0, valor_liquido=50),
                  linha(documento_fornecedor="00000000000010", fornecedor_nome="OUTRO GENERICO",
                        valor_documento=30, valor_glosa=0, valor_liquido=30)])
    construir_marts(con)
    flags = con.execute(
        "SELECT identificador, eh_documento_generico FROM marts.gasto_por_fornecedor "
        "WHERE identificador LIKE '0000000000%' AND periodo = '2024' ORDER BY 1"
    ).fetchall()
    assert flags == [("00000000000001", True), ("00000000000010", True)]
    raizes = {r[0] for r in con.execute(
        "SELECT raiz FROM marts.gasto_por_raiz WHERE periodo = '2024' AND eh_documento_generico"
    ).fetchall()}
    assert raizes == {"00000000000001", "00000000000010"}  # cada um é a própria raiz
    # Continuam como fornecedores externos: entram no total externo.
    assert float(con.execute(
        "SELECT gasto_total FROM marts.concentracao_fornecedores WHERE periodo = '2024'"
    ).fetchone()[0]) == 2410.0 + 80.0
