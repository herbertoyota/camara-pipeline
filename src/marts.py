"""Marts das perguntas de negócio, a partir de refined.

As regras ficam em sql/marts/*.sql. Este módulo executa os arquivos na ordem e
confere que os totais de cada mart batem com a base de gasto.

Depende de refined.despesas_deputado e refined.deputados (python -m src.clean e
python -m src.clean_camara).
"""

from pathlib import Path

import duckdb

PROJETO = Path(__file__).resolve().parent.parent
DB_PATH = PROJETO / "data" / "camara.duckdb"
SQL_DIR = PROJETO / "sql" / "marts"

# Ordem importa: a base vem primeiro; os marts de gasto dependem dela.
ARQUIVOS = (
    "base_gasto",
    "gasto_por_partido_ano",
    "gasto_por_uf_ano",
    "gasto_por_deputado_ano",
    "gasto_resumo_ano",
    "gasto_por_fornecedor",
    "top_fornecedores",
    "concentracao_fornecedores",
)


def _executar(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute((SQL_DIR / f"{nome}.sql").read_text(encoding="utf-8"))


def _soma(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    valor = con.execute(sql).fetchone()[0]
    return float(valor) if valor is not None else 0.0


def _conferir(con: duckdb.DuckDBPyConnection) -> None:
    """Falha se algum mart não somar o mesmo gasto que a base."""
    base = _soma(con, "SELECT sum(valor_liquido) FROM marts.base_gasto")
    base_linhas = _soma(con, "SELECT count(*) FROM marts.base_gasto")
    checagens = {
        "gasto_por_partido_ano": "SELECT sum(valor_liquido_total) FROM marts.gasto_por_partido_ano",
        "gasto_por_uf_ano": "SELECT sum(valor_liquido_total) FROM marts.gasto_por_uf_ano",
        "gasto_resumo_ano": "SELECT sum(valor_liquido_total) FROM marts.gasto_resumo_ano",
    }
    for mart, sql in checagens.items():
        if abs(_soma(con, sql) - base) > 0.005:
            raise RuntimeError(f"{mart} não soma o gasto da base")
    linhas_por_mart = {
        "gasto_por_partido_ano": "SELECT sum(linhas) FROM marts.gasto_por_partido_ano",
        "gasto_por_uf_ano": "SELECT sum(linhas) FROM marts.gasto_por_uf_ano",
        "gasto_resumo_ano": "SELECT sum(linhas) FROM marts.gasto_resumo_ano",
    }
    for mart, sql in linhas_por_mart.items():
        if _soma(con, sql) != base_linhas:
            raise RuntimeError(f"{mart} não tem o número de linhas da base")

    # Identificador de pessoa física é um prefixo do hash: dois CPFs não podem colidir nele.
    if _soma(con, "SELECT count(DISTINCT documento_fornecedor) - count(DISTINCT CASE WHEN tipo_documento_fornecedor = 'CNPJ' THEN documento_fornecedor ELSE 'ID-' || left(documento_fornecedor, 8) END) FROM marts.base_gasto") != 0:
        raise RuntimeError("colisão de identificador de fornecedor pessoa física")
    # Fornecedor sem documento quebraria o ranking e a concentração.
    if _soma(con, "SELECT count(*) FROM marts.base_gasto WHERE documento_fornecedor IS NULL") != 0:
        raise RuntimeError("há despesas sem documento de fornecedor")

    # Concentração: o gasto total de cada período bate com a base.
    for periodo, total in con.execute("SELECT periodo, gasto_total FROM marts.concentracao_fornecedores").fetchall():
        if periodo == "TOTAL":
            esperado = base
        else:
            esperado = _soma(con, f"SELECT sum(valor_liquido) FROM marts.base_gasto WHERE ano = {int(periodo)}")
        if abs(float(total) - esperado) > 0.005:
            raise RuntimeError(f"concentracao_fornecedores {periodo} não soma o gasto da base")

    # Top 10: 10 linhas por período quando há pelo menos 10 fornecedores.
    for periodo, n in con.execute("SELECT periodo, count(*) FROM marts.top_fornecedores GROUP BY 1").fetchall():
        fornecedores = con.execute(
            "SELECT fornecedores FROM marts.concentracao_fornecedores WHERE periodo = ?", [periodo]
        ).fetchone()[0]
        if n != min(10, fornecedores):
            raise RuntimeError(f"top_fornecedores {periodo} tem {n} linhas, esperado {min(10, fornecedores)}")

    # O mart por deputado cobre só deputados (sem liderança).
    gasto_deputados = _soma(con, "SELECT sum(valor_liquido) FROM marts.base_gasto WHERE NOT eh_lideranca")
    if abs(_soma(con, "SELECT sum(valor_liquido_total) FROM marts.gasto_por_deputado_ano") - gasto_deputados) > 0.005:
        raise RuntimeError("gasto_por_deputado_ano não soma o gasto de deputados")


def construir_marts(con: duckdb.DuckDBPyConnection) -> dict:
    """Recria os marts de gasto e devolve os totais de conferência."""
    con.execute("CREATE SCHEMA IF NOT EXISTS marts")
    for nome in ARQUIVOS:
        _executar(con, nome)
    _conferir(con)
    return {
        "top10_saldo_negativo": _soma(
            con, "SELECT count(*) FROM marts.top_fornecedores WHERE valor_liquido_total < 0"
        ),
        "resumo": con.execute(
            "SELECT ano, linhas, valor_liquido_total, valor_convencao_sinal, linhas_divergentes, "
            "deputados_com_despesa, gasto_medio_por_deputado FROM marts.gasto_resumo_ano ORDER BY ano"
        ).fetchall(),
    }


def carregar_marts(db_path: Path = DB_PATH) -> dict:
    with duckdb.connect(str(db_path)) as con:
        return construir_marts(con)


if __name__ == "__main__":
    with duckdb.connect(str(DB_PATH)) as con:
        for linha in construir_marts(con)["resumo"]:
            print(linha)
