"""Testes do desempate determinístico dos marts (mode / arg_max substituídos). Dados inventados.

Empate proposital: dois valores com a mesma contagem (ou o mesmo gasto). A regra é:
contagem decrescente e, no empate, ordem alfabética. Os valores empatados são inseridos com o
nome alfabeticamente MAIOR primeiro. Assim, um mode() que devolva o primeiro valor visto
(comportamento sem desempate) produz resultado diferente do esperado e o teste falha.

- Deputado 3 (id 3), mês 5 de 2024: partidos PSOL e PCdoB, 100 cada. Esperado: PCdoB.
  UFs RJ e SP, 100 cada. Esperado: RJ.
- Fornecedor CNPJ 66666666000166: nomes ZETA SERVICOS e ALFA SERVICOS, 100 cada. Esperado: ALFA SERVICOS.
  Categorias TELEFONIA e ALIMENTACAO, 100 cada. Esperado: ALIMENTACAO.
- Raiz 77777777 (dois CNPJs com 100 cada: ZETA e ALFA). Nome principal esperado: ALFA SERVICOS.
"""

import duckdb
import pytest

from src.marts import construir_marts


def despesa(**campos):
    base = {"ano_arquivo": 2024, "mes": 1, "id_deputado": None, "eh_lideranca": False,
            "sigla_partido": "AAA", "sigla_uf": "SP", "documento_fornecedor": "09296295000160",
            "tipo_documento_fornecedor": "CNPJ", "fornecedor_nome": "EMPRESA LTDA", "tipo_despesa": "TELEFONIA",
            "valor_documento": 100, "valor_glosa": 0, "valor_liquido": 100, "liquido_diverge": False}
    base.update(campos)
    return base


def inserir(con, linhas):
    for linha in linhas:
        colunas = ", ".join(linha)
        marcas = ", ".join("?" for _ in linha)
        con.execute(f"INSERT INTO refined.despesas_deputado ({colunas}) VALUES ({marcas})", list(linha.values()))


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("""CREATE TABLE refined.despesas_deputado (
        ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
        sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
        tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, tipo_despesa VARCHAR, valor_documento DECIMAL(18,2),
        valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2), liquido_diverge BOOLEAN,
        data_emissao DATE, id_documento BIGINT)""")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, uf_atual VARCHAR)")
    c.execute("CREATE TABLE refined.votos (id_votacao VARCHAR, id_deputado INTEGER, tipo_voto VARCHAR, data_votacao DATE, sigla_orgao VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (3, 'Dep Tres', 'RJ')")
    inserir(c, [
        # Deputado 3: empate de partido e de UF no mês 5 (o último mês com despesa).
        despesa(id_deputado=3, mes=5, sigla_partido="PSOL", sigla_uf="SP", fornecedor_nome="ZETA SERVICOS",
                documento_fornecedor="66666666000166"),
        despesa(id_deputado=3, mes=5, sigla_partido="PCdoB", sigla_uf="RJ", fornecedor_nome="ALFA SERVICOS",
                documento_fornecedor="66666666000166", tipo_despesa="ALIMENTACAO"),
        # Fornecedor 66666666000166: nomes e categorias empatados (1 linha cada, já em ordem inversa).
        # Raiz 77777777: dois CNPJs com o mesmo gasto (100), o de nome maior entra primeiro.
        despesa(id_deputado=3, mes=1, sigla_partido="PSOL", sigla_uf="RJ", fornecedor_nome="ZETA SERVICOS",
                documento_fornecedor="77777777000177"),
        despesa(id_deputado=3, mes=1, sigla_partido="PSOL", sigla_uf="RJ", fornecedor_nome="ALFA SERVICOS",
                documento_fornecedor="77777777000258"),
    ])
    construir_marts(c)
    yield c
    c.close()


def valor_unico(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


def test_empate_de_partido_e_uf_no_mes_escolhe_alfabetico(con):
    partido, uf = con.execute(
        "SELECT partido, uf FROM marts.gasto_por_deputado_mes WHERE id_deputado = 3 AND mes = 5"
    ).fetchone()
    assert partido == "PCdoB"
    assert uf == "RJ"


def test_empate_de_partido_e_uf_no_ano_usa_o_ultimo_mes_e_alfabetico(con):
    partido, uf = con.execute(
        "SELECT partido, uf FROM marts.gasto_por_deputado_ano WHERE id_deputado = 3"
    ).fetchone()
    assert partido == "PCdoB"
    assert uf == "RJ"


def test_empate_de_nome_e_categoria_do_fornecedor_escolhe_alfabetico(con):
    nome, categoria = con.execute(
        "SELECT fornecedor_nome, tipo_despesa_predominante FROM marts.gasto_por_fornecedor "
        "WHERE periodo = 'TOTAL' AND identificador = '66666666000166'"
    ).fetchone()
    assert nome == "ALFA SERVICOS"
    assert categoria == "ALIMENTACAO"


def test_empate_de_gasto_no_nome_principal_da_raiz_escolhe_alfabetico(con):
    nome = valor_unico(con, "SELECT nome_principal FROM marts.gasto_por_raiz WHERE periodo = '2024' AND raiz = '77777777'")
    assert nome == "ALFA SERVICOS"


def test_resultado_nao_depende_da_ordem_das_linhas():
    """Mesmas despesas em ordem inversa dão o mesmo mart."""
    def montar(ordem):
        c = duckdb.connect(":memory:")
        c.execute("CREATE SCHEMA refined")
        c.execute("""CREATE TABLE refined.despesas_deputado (
            ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
            sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
            tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, tipo_despesa VARCHAR, valor_documento DECIMAL(18,2),
            valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2), liquido_diverge BOOLEAN,
            data_emissao DATE, id_documento BIGINT)""")
        c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, uf_atual VARCHAR)")
        c.execute("CREATE TABLE refined.votos (id_votacao VARCHAR, id_deputado INTEGER, tipo_voto VARCHAR, data_votacao DATE, sigla_orgao VARCHAR)")
        c.execute("INSERT INTO refined.deputados VALUES (3, 'Dep Tres', 'RJ')")
        linhas = [
            despesa(id_deputado=3, mes=5, sigla_partido="PSOL", fornecedor_nome="ZETA SERVICOS", documento_fornecedor="66666666000166"),
            despesa(id_deputado=3, mes=5, sigla_partido="PCdoB", fornecedor_nome="ALFA SERVICOS", documento_fornecedor="66666666000166"),
        ]
        inserir(c, linhas if ordem == "direta" else list(reversed(linhas)))
        construir_marts(c)
        resultado = c.execute(
            "SELECT partido FROM marts.gasto_por_deputado_mes WHERE id_deputado = 3"
        ).fetchone()[0], c.execute(
            "SELECT fornecedor_nome FROM marts.gasto_por_fornecedor WHERE periodo = 'TOTAL' AND identificador = '66666666000166'"
        ).fetchone()[0]
        c.close()
        return resultado

    assert montar("direta") == montar("inversa") == ("PCdoB", "ALFA SERVICOS")
