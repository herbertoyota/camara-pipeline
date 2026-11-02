"""Privacidade dos marts: nenhuma coluna nem valor de documento, URL ou hash no schema marts.

Dados inventados, DuckDB em memória. O hash vem de um CPF inventado e não é um CPF real.
"""

import hashlib
import re

import duckdb
import pytest

from src.marts import construir_marts

HASH_PF = hashlib.sha256(b"sal-teste|11111111111").hexdigest()
COLUNAS_PROIBIDAS_NOS_MARTS = {"documento_fornecedor", "id_documento", "num_documento", "url_documento"}


def despesa(**campos):
    base = {"ano_arquivo": 2024, "mes": 1, "id_deputado": 1, "eh_lideranca": False,
            "sigla_partido": "AAA", "sigla_uf": "SP", "documento_fornecedor": "66666666000166",
            "tipo_documento_fornecedor": "CNPJ", "fornecedor_nome": "EMPRESA LTDA", "tipo_despesa": "TELEFONIA",
            "valor_documento": 100, "valor_glosa": 0, "valor_liquido": 100, "liquido_diverge": False,
            "id_documento": 1}
    base.update(campos)
    return base


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
    c.execute("INSERT INTO refined.deputados VALUES (1, 'Dep Um', 'SP')")
    linhas = [
        despesa(),
        despesa(mes=2, documento_fornecedor=HASH_PF, tipo_documento_fornecedor="CPF",
                fornecedor_nome="PESSOA FISICA", id_documento=2, data_emissao="2024-01-06"),
    ]
    for linha in linhas:
        colunas = ", ".join(linha)
        marcas = ", ".join("?" for _ in linha)
        c.execute(f"INSERT INTO refined.despesas_deputado ({colunas}) VALUES ({marcas})", list(linha.values()))
    construir_marts(c)
    yield c
    c.close()


def colunas_dos_marts(con):
    return con.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'marts'"
    ).fetchall()


def test_marts_nao_tem_coluna_de_documento_nem_url(con):
    proibidas = [(t, c) for t, c in colunas_dos_marts(con) if c in COLUNAS_PROIBIDAS_NOS_MARTS]
    assert proibidas == []


def test_marts_nao_tem_hash_completo_em_nenhum_valor(con):
    padrao = re.compile(r"^[0-9a-f]{64}$")
    achados = 0
    for tabela, coluna in colunas_dos_marts(con):
        tipo = con.execute(
            "SELECT data_type FROM information_schema.columns WHERE table_schema = 'marts' "
            "AND table_name = ? AND column_name = ?", [tabela, coluna]
        ).fetchone()[0]
        if tipo != "VARCHAR":
            continue
        for (valor,) in con.execute(f'SELECT "{coluna}" FROM marts."{tabela}"').fetchall():
            if valor is not None and padrao.match(valor):
                achados += 1
    assert achados == 0


def test_base_intermediaria_fica_fora_do_schema_marts(con):
    schemas = {r[0] for r in con.execute(
        "SELECT table_schema FROM information_schema.tables WHERE table_name = 'base_gasto'").fetchall()}
    assert schemas == {"intermediario"}


def test_base_intermediaria_nao_tem_hash_completo(con):
    colunas = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'intermediario' "
        "AND table_name = 'base_gasto'").fetchall()}
    assert "documento_fornecedor" not in colunas
    assert "identificador_fornecedor" in colunas
    assert con.execute(
        "SELECT identificador_fornecedor FROM intermediario.base_gasto WHERE tipo_documento_fornecedor = 'CPF'"
    ).fetchone()[0] == "ID-" + HASH_PF[:8]
