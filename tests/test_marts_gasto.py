"""Testes dos marts de gasto (pergunta 1). Dados inventados, DuckDB em memória.

Conjunto (ano 2024), conferido à mão:
- D1 (id 1, AAA, SP): 100 (mês 1), estorno -30 (mês 2), 100 com líquido 80 e divergência (mês 3). Total 150.
- D2 (id 2, BBB em março, CCC em maio, MG): 200 (mês 1), convenção de sinal -60 (mês 2), 50 (mês 3, CCC). Total 190.
- L (liderança, sem id, UF NA, partido LIDERANCA): 40. Total 40.
Gasto total = 380. Convenção = -60. Divergentes = 1. Deputados com despesa = 2.
Gasto médio por deputado = (150 + 190) / 2 = 170 (liderança fora do numerador e do denominador).
"""

import duckdb
import pytest

from src.marts import construir_marts


def inserir(con, linhas):
    for linha in linhas:
        colunas = ", ".join(linha)
        marcas = ", ".join("?" for _ in linha)
        con.execute(f"INSERT INTO refined.despesas_deputado ({colunas}) VALUES ({marcas})", list(linha.values()))


def despesa(**campos):
    base = {"ano_arquivo": 2024, "mes": 1, "id_deputado": None, "eh_lideranca": False,
            "sigla_partido": "AAA", "sigla_uf": "SP", "documento_fornecedor": "09296295000160",
            "tipo_documento_fornecedor": "CNPJ", "fornecedor_nome": "EMPRESA LTDA",
            "valor_documento": 0, "valor_glosa": 0, "valor_liquido": 0, "liquido_diverge": False}
    base.update(campos)
    return base


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("""CREATE TABLE refined.despesas_deputado (
        ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
        sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
        tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, valor_documento DECIMAL(18,2),
        valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2), liquido_diverge BOOLEAN)""")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1, 'Dep Um'), (2, 'Dep Dois')")
    inserir(c, [
        despesa(id_deputado=1, mes=1, sigla_partido="AAA", sigla_uf="SP", valor_documento=100, valor_glosa=0, valor_liquido=100),
        despesa(id_deputado=1, mes=2, sigla_partido="AAA", sigla_uf="SP", valor_documento=-30, valor_glosa=0, valor_liquido=-30),
        despesa(id_deputado=1, mes=3, sigla_partido="AAA", sigla_uf="SP", valor_documento=100, valor_glosa=0,
                valor_liquido=80, liquido_diverge=True),
        despesa(id_deputado=2, mes=1, sigla_partido="BBB", sigla_uf="MG", valor_documento=200, valor_glosa=0, valor_liquido=200),
        despesa(id_deputado=2, mes=2, sigla_partido="BBB", sigla_uf="MG", valor_documento=60, valor_glosa=None, valor_liquido=-60, liquido_diverge=True),
        despesa(id_deputado=2, mes=3, sigla_partido="CCC", sigla_uf="MG", valor_documento=50, valor_glosa=0, valor_liquido=50),
        despesa(id_deputado=None, eh_lideranca=True, mes=1, sigla_partido=None, sigla_uf="NA",
                fornecedor_nome="TELEFONIA", valor_documento=40, valor_glosa=0, valor_liquido=40),
    ])
    construir_marts(c)
    yield c
    c.close()


def valor(x):
    return float(x) if x is not None else None


# --- totais e estorno ------------------------------------------------------

def test_gasto_total_do_ano_bate_com_a_base(con):
    total = con.execute("SELECT valor_liquido_total FROM marts.gasto_resumo_ano WHERE ano = 2024").fetchone()[0]
    assert valor(total) == 380.0


def test_estorno_abate_o_total_do_deputado(con):
    total = con.execute("SELECT valor_liquido_total FROM marts.gasto_por_deputado_ano WHERE id_deputado = 1").fetchone()[0]
    assert valor(total) == 150.0  # 100 - 30 + 80


def test_convencao_de_sinal_fica_separada_e_abate(con):
    conv = con.execute("SELECT valor_convencao_sinal FROM marts.gasto_resumo_ano WHERE ano = 2024").fetchone()[0]
    assert valor(conv) == -60.0
    total_d2 = con.execute("SELECT valor_liquido_total, valor_convencao_sinal FROM marts.gasto_por_deputado_ano WHERE id_deputado = 2").fetchone()
    assert (valor(total_d2[0]), valor(total_d2[1])) == (190.0, -60.0)


def test_linhas_divergentes_sao_contadas_e_entram_no_total(con):
    div = con.execute("SELECT linhas_divergentes, valor_liquido_total FROM marts.gasto_resumo_ano WHERE ano = 2024").fetchone()
    assert div[0] == 1
    assert valor(div[1]) == 380.0  # divergente entra no padrão


# --- denominador e liderança ----------------------------------------------

def test_gasto_medio_por_deputado_tem_denominador_certo(con):
    medio = con.execute("SELECT deputados_com_despesa, gasto_medio_por_deputado FROM marts.gasto_resumo_ano WHERE ano = 2024").fetchone()
    assert medio[0] == 2
    assert valor(medio[1]) == 170.0  # (150 + 190) / 2; liderança não entra


def test_lideranca_fica_fora_do_mart_por_deputado(con):
    ids = {r[0] for r in con.execute("SELECT id_deputado FROM marts.gasto_por_deputado_ano").fetchall()}
    assert ids == {1, 2}


def test_lideranca_fica_dentro_do_mart_por_partido(con):
    liderancas = con.execute(
        "SELECT valor_liquido_total, deputados_com_despesa, gasto_medio_por_deputado "
        "FROM marts.gasto_por_partido_ano WHERE partido = 'LIDERANCA'"
    ).fetchone()
    assert valor(liderancas[0]) == 40.0
    assert liderancas[1] == 0
    assert liderancas[2] is None


def test_partido_e_o_da_epoca_do_gasto(con):
    # D2 trocou de BBB para CCC: cada gasto fica no partido do seu mês.
    por_partido = {r[0]: valor(r[1]) for r in con.execute(
        "SELECT partido, valor_liquido_total FROM marts.gasto_por_partido_ano WHERE ano = 2024").fetchall()}
    assert por_partido == {"AAA": 150.0, "BBB": 140.0, "CCC": 50.0, "LIDERANCA": 40.0}


def test_deputado_que_trocou_de_partido_aparece_com_o_partido_mais_recente(con):
    partido = con.execute("SELECT partido FROM marts.gasto_por_deputado_ano WHERE id_deputado = 2").fetchone()[0]
    assert partido == "CCC"


def test_mart_por_uf_inclui_lideranca_como_NA(con):
    por_uf = {r[0]: valor(r[1]) for r in con.execute(
        "SELECT uf, valor_liquido_total FROM marts.gasto_por_uf_ano WHERE ano = 2024").fetchall()}
    assert por_uf == {"SP": 150.0, "MG": 190.0, "NA": 40.0}
