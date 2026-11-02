"""Testes do mart de crescimento por categoria (pergunta 3). Dados inventados, DuckDB em memória.

Categorias (valor líquido por ano):
- ALFA: 2023 100, 2024 150, 2025 200 -> +100 (+100%) em 2023→2025; +50% e +33,3%.
- BETA: só 2023 (100) -> ausente em 2024 e 2025; percentuais NULL.
- GAMA: só 2024 (50) e 2025 (80) -> base 2023 zero; 2023→2025 NULL; 2024→2025 = +60%.
- NEG: -50, -60, -40 (base negativa) -> percentuais NULL; base_nao_positiva = TRUE.
"""

import duckdb
import pytest

from src.marts import construir_marts


def inserir(con, linhas):
    for ano, cat, valor in linhas:
        con.execute(
            "INSERT INTO refined.despesas_deputado (ano_arquivo, mes, id_deputado, eh_lideranca, sigla_partido, "
            "sigla_uf, documento_fornecedor, tipo_documento_fornecedor, fornecedor_nome, tipo_despesa, "
            "valor_documento, valor_glosa, valor_liquido, liquido_diverge) "
            "VALUES (?, 1, 1, FALSE, 'AAA', 'SP', '09296295000160', 'CNPJ', 'EMPRESA LTDA', ?, ?, 0, ?, FALSE)",
            [ano, cat, valor, valor],
        )


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("""CREATE TABLE refined.despesas_deputado (
        ano_arquivo INTEGER, mes INTEGER, id_deputado INTEGER, eh_lideranca BOOLEAN,
        sigla_partido VARCHAR, sigla_uf VARCHAR, documento_fornecedor VARCHAR,
        tipo_documento_fornecedor VARCHAR, fornecedor_nome VARCHAR, tipo_despesa VARCHAR,
        valor_documento DECIMAL(18,2), valor_glosa DECIMAL(18,2), valor_liquido DECIMAL(18,2),
        liquido_diverge BOOLEAN,
        data_emissao DATE, id_documento BIGINT)""")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, uf_atual VARCHAR)")
    c.execute("CREATE TABLE refined.votos (id_votacao VARCHAR, id_deputado INTEGER, tipo_voto VARCHAR, data_votacao DATE, sigla_orgao VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1, 'Dep Um', 'SP')")
    inserir(c, [
        (2023, "ALFA", 100), (2024, "ALFA", 150), (2025, "ALFA", 200),
        (2023, "BETA", 100),
        (2024, "GAMA", 50), (2025, "GAMA", 80),
        (2023, "NEG", -50), (2024, "NEG", -60), (2025, "NEG", -40),
    ])
    construir_marts(c)
    yield c
    c.close()


def cat(con, nome):
    cur = con.execute("SELECT * FROM marts.crescimento_categorias WHERE tipo_despesa = ?", [nome])
    nomes = [d[0] for d in cur.description]
    return dict(zip(nomes, cur.fetchone()))


def test_crescimento_absoluto_e_percentual(con):
    r = cat(con, "ALFA")
    assert float(r["var_abs_2023_2025"]) == 100.0
    assert float(r["var_pct_2023_2025"]) == pytest.approx(100.0)
    assert float(r["var_pct_2023_2024"]) == pytest.approx(50.0)
    assert float(r["var_pct_2024_2025"]) == pytest.approx(100.0 / 3, abs=5e-5)
    assert r["presente_em_todos_os_anos"] is True and r["anos_ausentes"] is None


def test_categoria_que_some_fica_sinalizada_e_sem_percentual(con):
    r = cat(con, "BETA")
    assert r["presente_em_todos_os_anos"] is False
    assert r["anos_ausentes"] == "2024 2025"
    assert r["var_pct_2023_2025"] is None and r["var_pct_2023_2024"] is None


def test_categoria_que_surge_com_base_zero_nao_tem_percentual_no_periodo(con):
    r = cat(con, "GAMA")
    assert r["anos_ausentes"] == "2023"
    assert r["var_pct_2023_2025"] is None  # base 2023 zero
    assert float(r["var_pct_2024_2025"]) == pytest.approx(60.0)  # 2024 e 2025 têm base positiva


def test_base_negativa_nao_gera_percentual(con):
    r = cat(con, "NEG")
    assert r["base_nao_positiva"] is True
    assert r["var_pct_2023_2025"] is None and r["var_pct_2023_2024"] is None
    assert float(r["var_abs_2023_2025"]) == 10.0  # absoluto continua valendo: -40 - (-50)


def test_familia_passagem_aerea_soma_as_tres_categorias_e_fica_marcada(con):
    inserir(con, [
        (2023, "PASSAGEM AÉREA - SIGEPA", 100), (2025, "PASSAGEM AÉREA - SIGEPA", 50),
        (2024, "PASSAGEM AÉREA - RPA", 10),
        (2025, "PASSAGEM AÉREA - MISSÃO OFICIAL", -5),
        (2023, "PASSAGEM AÉREA - REEMBOLSO", 999),  # fora da família
    ])
    construir_marts(con)
    fam = cat(con, "FAMILIA PASSAGEM AEREA (SIGEPA + RPA + MISSAO OFICIAL)")
    assert fam["eh_agregado"] is True
    assert float(fam["valor_2023"]) == 100.0 and float(fam["valor_2025"]) == 45.0  # 50 - 5
    assert float(fam["var_pct_2023_2025"]) == pytest.approx(-55.0)
    assert cat(con, "PASSAGEM AÉREA - SIGEPA")["eh_agregado"] is False
