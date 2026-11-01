"""Limpeza de deputados e votos: raw -> refined.deputados, refined.votos e a ponte.

As regras ficam em sql/refined/*.sql. Este módulo executa os três arquivos na
ordem (a ponte depende de deputados e de refined.despesas), confere as contagens
e calcula a taxa de linhas sem par no JOIN despesas x deputados.

Depende de refined.despesas já criada (python -m src.clean).
"""

from pathlib import Path

import duckdb

PROJETO = Path(__file__).resolve().parent.parent
DB_PATH = PROJETO / "data" / "camara.duckdb"
SQL_DIR = PROJETO / "sql" / "refined"

# Ordem importa: ponte_deputado_ceap lê refined.deputados e refined.despesas.
TABELAS = ("deputados", "votos", "ponte_deputado_ceap")
ANOS = (2023, 2024, 2025)


def _executar(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute((SQL_DIR / f"{nome}.sql").read_text(encoding="utf-8"))


def _contar(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def _conferir(con: duckdb.DuckDBPyConnection) -> None:
    """Falha se alguma contagem não bater com o raw ou se houver chave duplicada."""
    raw_deputados = _contar(con, "SELECT count(*) FROM raw.deputados")
    if _contar(con, "SELECT count(*) FROM refined.deputados") != raw_deputados:
        raise RuntimeError("refined.deputados não tem o mesmo número de linhas do raw.deputados")
    if _contar(con, "SELECT count(*) - count(DISTINCT id_deputado) FROM refined.deputados") != 0:
        raise RuntimeError("refined.deputados tem id_deputado duplicado")
    if _contar(con, "SELECT count(*) FROM refined.deputados WHERE id_deputado IS NULL") != 0:
        raise RuntimeError("refined.deputados tem linha sem id_deputado")

    raw_votos = sum(_contar(con, f"SELECT count(*) FROM raw.votacoes_votos_{a}") for a in ANOS)
    if _contar(con, "SELECT count(*) FROM refined.votos") != raw_votos:
        raise RuntimeError(
            "refined.votos perdeu votos: votos de votações fora de 2023-2025 ou sem votação correspondente"
        )
    if _contar(con, "SELECT count(*) - count(DISTINCT (id_votacao, id_deputado)) FROM refined.votos") != 0:
        raise RuntimeError("refined.votos tem (votação, deputado) duplicado")

    if _contar(con, "SELECT count(*) - count(DISTINCT (ano_arquivo, nu_deputado_id)) FROM refined.ponte_deputado_ceap") != 0:
        raise RuntimeError("refined.ponte_deputado_ceap tem (ano, id CEAP) duplicado")


def taxa_sem_par(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Por ano: linhas de despesa, linhas com par por método e linhas sem par.

    Sem par = a linha de despesa não encontra deputado no cadastro pelo id da
    ponte. Linhas de liderança partidária (UF 'NA') são contadas à parte.
    """
    return con.execute(
        """
        SELECT
            d.ano_arquivo,
            count(*)                                                        AS linhas,
            count(*) FILTER (WHERE p.metodo = 'votos')                      AS por_votos,
            count(*) FILTER (WHERE p.metodo = 'cadastro_unico')             AS por_cadastro_unico,
            count(*) FILTER (WHERE p.id_deputado IS NULL AND d.sigla_uf = 'NA')  AS sem_par_lideranca,
            count(*) FILTER (WHERE p.id_deputado IS NULL AND d.sigla_uf <> 'NA') AS sem_par_deputado
        FROM refined.despesas d
        LEFT JOIN refined.ponte_deputado_ceap p
            ON p.ano_arquivo = d.ano_arquivo AND p.nu_deputado_id = d.nu_deputado_id
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()


def ids_sem_par(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Ids do CEAP (deputado, não liderança) sem par, com nome, UF e linhas afetadas."""
    return con.execute(
        """
        SELECT d.ano_arquivo, d.nu_deputado_id, any_value(d.nome_parlamentar) AS nome, any_value(d.sigla_uf) AS uf,
               count(*) AS linhas
        FROM refined.despesas d
        LEFT JOIN refined.ponte_deputado_ceap p
            ON p.ano_arquivo = d.ano_arquivo AND p.nu_deputado_id = d.nu_deputado_id
        WHERE p.id_deputado IS NULL AND d.sigla_uf <> 'NA'
        GROUP BY 1, 2
        ORDER BY 1, 5 DESC
        """
    ).fetchall()


def construir_refined_camara(con: duckdb.DuckDBPyConnection) -> dict:
    """Recria refined.deputados, refined.votos e refined.ponte_deputado_ceap."""
    con.execute("CREATE SCHEMA IF NOT EXISTS refined")
    for tabela in TABELAS:
        _executar(con, tabela)
    _conferir(con)
    return {
        "deputados": _contar(con, "SELECT count(*) FROM refined.deputados"),
        "votos": _contar(con, "SELECT count(*) FROM refined.votos"),
        "ponte": con.execute(
            "SELECT metodo, count(*) FROM refined.ponte_deputado_ceap GROUP BY 1 ORDER BY 1"
        ).fetchall(),
    }


def carregar_refined_camara(db_path: Path = DB_PATH) -> dict:
    with duckdb.connect(str(db_path)) as con:
        return construir_refined_camara(con)


if __name__ == "__main__":
    with duckdb.connect(str(DB_PATH)) as con:
        print(construir_refined_camara(con))
        for linha in taxa_sem_par(con):
            print(linha)
