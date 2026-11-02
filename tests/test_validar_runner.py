"""Testes do comparador da validação do runner (src/validar_runner.py). Dados inventados, arquivos em tmp_path."""

import duckdb

from src.validar_runner import comparar_bancos


def criar_banco(caminho, linhas):
    with duckdb.connect(str(caminho)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute("CREATE TABLE marts.t (chave VARCHAR, valor DOUBLE, decimal_exato DECIMAL(18,2))")
        con.executemany("INSERT INTO marts.t VALUES (?, ?, ?)", linhas)


def test_double_dentro_da_tolerancia_nao_conta(tmp_path):
    a, b = tmp_path / "a.duckdb", tmp_path / "b.duckdb"
    criar_banco(a, [("x", 33.3333333, 1.10), ("y", None, 2.00)])
    criar_banco(b, [("x", 33.3333333 + 5e-7, 1.10), ("y", None, 2.00)])
    assert comparar_bancos(a, b)["diferencas"] == 0


def test_double_fora_da_tolerancia_conta(tmp_path):
    a, b = tmp_path / "a.duckdb", tmp_path / "b.duckdb"
    criar_banco(a, [("x", 33.3333, 1.10)])
    criar_banco(b, [("x", 33.3340, 1.10)])
    resultado = comparar_bancos(a, b)
    assert resultado["diferencas"] == 1
    assert "valor" in resultado["exemplos"][0]


def test_decimal_e_texto_sao_comparados_por_igualdade_exata(tmp_path):
    a, b = tmp_path / "a.duckdb", tmp_path / "b.duckdb"
    criar_banco(a, [("x", 1.0, 1.10)])
    criar_banco(b, [("x", 1.0, 1.11)])
    assert comparar_bancos(a, b)["diferencas"] == 1


def test_numero_de_linhas_diferente_conta(tmp_path):
    a, b = tmp_path / "a.duckdb", tmp_path / "b.duckdb"
    criar_banco(a, [("x", 1.0, 1.10), ("y", 2.0, 2.20)])
    criar_banco(b, [("x", 1.0, 1.10)])
    resultado = comparar_bancos(a, b)
    assert resultado["diferencas"] == 1
    assert "linhas" in resultado["exemplos"][0]
