"""Testes dos indicadores de atipicidade (pergunta 5). Dados inventados, DuckDB em memória.

Valores conhecidos:
- CAT (2024, 100 linhas positivas com valores 1..100): p99 = 99,01 (interpolação linear); mediana = 50,5.
  Só o valor 100 é > p99. Razão do valor 100 sobre a mediana = 100 / 50,5.
- PEQ (2024, 99 linhas): abaixo de 100 linhas, todos os indicadores de valor são NULL.
- Fim de semana: 2024-06-08 é sábado; 2024-06-10 é segunda.
- Mesmo fornecedor, mesmo dia, mesmo deputado: 2 documentos distintos -> TRUE; sem id_documento -> NULL.
- Estornos (valor <= 0) e liderança ficam fora do mart.
"""

from datetime import date, timedelta

import duckdb
import pytest

from src.marts import _executar

CNPJ = "11111111000111"


def inserir(con, linhas):
    for l in linhas:
        con.execute(
            "INSERT INTO refined.despesas_deputado (ano_arquivo, mes, id_deputado, eh_lideranca, sigla_partido, "
            "sigla_uf, documento_fornecedor, tipo_documento_fornecedor, fornecedor_nome, tipo_despesa, "
            "valor_documento, valor_glosa, valor_liquido, liquido_diverge, data_emissao, id_documento) "
            "VALUES (?, ?, ?, ?, 'AAA', 'SP', ?, 'CNPJ', 'EMPRESA', ?, ?, 0, ?, FALSE, ?, ?)",
            [l["ano"], l.get("mes", 1), l["dep"], l.get("lid", False), l.get("doc", CNPJ), l["cat"],
             l["valor"], l["valor"], l.get("data"), l.get("id")])


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE SCHEMA marts")
    c.execute("""CREATE TABLE refined.despesas_deputado (
        ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
        sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
        tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, tipo_despesa VARCHAR,
        valor_documento DECIMAL(18,2), valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2),
        liquido_diverge BOOLEAN, data_emissao DATE, id_documento BIGINT)""")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, uf_atual VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1,'Dep 1','SP'),(2,'Dep 2','SP'),(3,'Dep 3','SP'),"
              "(4,'Dep 4','SP'),(5,'Dep 5','SP')")
    base = date(2024, 1, 1)
    linhas = []
    for i in range(1, 101):  # CAT: 1..100
        linhas.append({"ano": 2024, "dep": 1, "cat": "CAT", "valor": i, "data": base + timedelta(days=i), "id": 10000 + i})
    for i in range(1, 100):  # PEQ: 99 linhas
        linhas.append({"ano": 2024, "dep": 5, "cat": "PEQ", "valor": 10, "data": base + timedelta(days=i), "id": 20000 + i})
    sab, seg = date(2024, 6, 8), date(2024, 6, 10)
    linhas += [
        {"ano": 2024, "dep": 2, "cat": "FDS", "valor": 10, "data": sab, "id": 301},
        {"ano": 2024, "dep": 2, "cat": "FDS", "valor": 10, "data": seg, "id": 302},
        {"ano": 2024, "dep": 2, "cat": "FDS", "valor": 10, "data": None, "id": 303},
        {"ano": 2024, "dep": 3, "cat": "MESMO", "valor": 10, "data": sab, "id": 401},
        {"ano": 2024, "dep": 3, "cat": "MESMO", "valor": 10, "data": sab, "id": 402},
        {"ano": 2024, "dep": 3, "cat": "MESMO", "valor": 10, "data": sab, "id": None},
        {"ano": 2024, "dep": 4, "cat": "MESMO", "valor": 10, "data": sab, "id": 403},
        {"ano": 2024, "dep": 1, "cat": "CAT", "valor": -5, "data": base, "id": 999},          # estorno
        {"ano": 2024, "dep": 1, "cat": "CAT", "valor": 10, "data": base, "id": 998, "lid": True},  # liderança
    ]
    inserir(c, linhas)
    _executar(c, "base_gasto")
    _executar(c, "indicadores_despesa_atipica")
    yield c
    c.close()


def linha(con, dep, cat, valor=None, id_=None):
    q = "SELECT * FROM marts.indicadores_despesa_atipica WHERE id_deputado = ? AND tipo_despesa = ?"
    params = [dep, cat]
    if valor is not None:
        q += " AND valor_liquido = ?"
        params.append(valor)
    cur = con.execute(q, params)
    nomes = [d[0] for d in cur.description]
    return dict(zip(nomes, cur.fetchone()))


def test_p99_e_mediana_com_valores_conhecidos(con):
    r100 = linha(con, 1, "CAT", 100)
    assert r100["valor_acima_do_p99_da_categoria"] is True
    assert r100["razao_sobre_mediana_categoria"] == pytest.approx(100 / 50.5)
    assert linha(con, 1, "CAT", 99)["valor_acima_do_p99_da_categoria"] is False  # 99 < 99,01
    assert linha(con, 1, "CAT", 50)["valor_acima_do_p99_da_categoria"] is False


def test_categoria_com_menos_de_100_linhas_tem_indicador_nulo(con):
    r = linha(con, 5, "PEQ")
    assert r["valor_acima_do_p99_da_categoria"] is None and r["razao_sobre_mediana_categoria"] is None


def test_fim_de_semana_usa_a_data_e_fica_nulo_sem_data(con):
    assert linha(con, 2, "FDS", 10)  # uma das linhas com sábado
    sab = con.execute("SELECT emissao_fim_de_semana FROM marts.indicadores_despesa_atipica WHERE id_deputado = 2 AND data_emissao = DATE '2024-06-08'").fetchone()[0]
    seg = con.execute("SELECT emissao_fim_de_semana FROM marts.indicadores_despesa_atipica WHERE id_deputado = 2 AND data_emissao = DATE '2024-06-10'").fetchone()[0]
    nula = con.execute("SELECT emissao_fim_de_semana FROM marts.indicadores_despesa_atipica WHERE id_deputado = 2 AND data_emissao IS NULL").fetchone()[0]
    assert (sab, seg, nula) == (True, False, None)


def test_mesmo_fornecedor_mesmo_dia_exige_dois_documentos(con):
    # Dep 3: duas linhas com documentos distintos no mesmo dia (TRUE) e uma sem id (NULL).
    # O mart não expõe id_documento, então as linhas são distinguidas pelo conjunto de flags.
    flags = [r[0] for r in con.execute(
        "SELECT mesmo_fornecedor_mesmo_dia_mesmo_deputado FROM marts.indicadores_despesa_atipica "
        "WHERE id_deputado = 3").fetchall()]
    assert sorted(flags, key=lambda v: (v is None, v)) == [True, True, None]
    assert con.execute("SELECT mesmo_fornecedor_mesmo_dia_mesmo_deputado FROM marts.indicadores_despesa_atipica "
                       "WHERE id_deputado = 4").fetchone()[0] is False


def test_estorno_e_lideranca_ficam_fora(con):
    assert con.execute("SELECT count(*) FROM marts.indicadores_despesa_atipica WHERE valor_liquido <= 0").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM marts.indicadores_despesa_atipica WHERE id_deputado IS NULL").fetchone()[0] == 0


def test_motivos_contagem_soma_os_indicadores(con):
    # Dep 3 (sábado): as duas linhas com documentos distintos -> fim de semana + mesmo dia = 2;
    # a linha sem id -> só fim de semana = 1. Valor não se aplica (categoria com 3 linhas).
    motivos = sorted(r[0] for r in con.execute(
        "SELECT motivos_contagem FROM marts.indicadores_despesa_atipica WHERE id_deputado = 3").fetchall())
    assert motivos == [1, 2, 2]


def test_mart_nao_tem_colunas_proibidas(con):
    colunas = {c[0] for c in con.execute("DESCRIBE marts.indicadores_despesa_atipica").fetchall()}
    assert not colunas & {"num_documento", "url_documento", "documento_fornecedor", "fornecedor_nome"}


def test_mesmo_valor_exige_valor_identico(con):
    # Dep 4 tem uma linha com documento 403 de valor 10, no mesmo dia que a de dep 3: não é do mesmo deputado.
    # Dep 3: as duas linhas com valor 10 e documentos distintos no mesmo dia são TRUE; a sem id é NULL.
    flags = sorted([r[0] for r in con.execute(
        "SELECT mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado FROM marts.indicadores_despesa_atipica "
        "WHERE id_deputado = 3").fetchall()], key=lambda v: (v is None, v))
    assert flags == [True, True, None]
    assert con.execute("SELECT mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado FROM marts.indicadores_despesa_atipica "
                       "WHERE id_deputado = 4").fetchone()[0] is False
