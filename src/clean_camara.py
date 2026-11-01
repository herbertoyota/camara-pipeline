"""Limpeza de deputados e votos: raw -> refined.deputados, refined.votos, a ponte e a view de despesas por deputado.

As regras ficam em sql/refined/*.sql. Este módulo executa os arquivos na ordem
(deputados lê refined.despesas; a ponte lê deputados; a view lê a ponte), confere
as contagens e calcula a taxa de linhas sem par no JOIN despesas x deputados.

Depende de refined.despesas já criada (python -m src.clean).
"""

from pathlib import Path

import duckdb

PROJETO = Path(__file__).resolve().parent.parent
DB_PATH = PROJETO / "data" / "camara.duckdb"
SQL_DIR = PROJETO / "sql" / "refined"

# Ordem importa: deputados lê despesas; ponte lê deputados; a view lê a ponte.
TABELAS = ("deputados", "votos", "ponte_deputado_ceap", "despesas_deputado")
ANOS = (2023, 2024, 2025)


def _executar(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute((SQL_DIR / f"{nome}.sql").read_text(encoding="utf-8"))


def _contar(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def _conferir(con: duckdb.DuckDBPyConnection) -> None:
    """Falha se alguma contagem não bater com a origem ou se houver chave duplicada."""
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

    if _contar(con, "SELECT count(*) FROM refined.despesas_deputado") != _contar(con, "SELECT count(*) FROM refined.despesas"):
        raise RuntimeError("refined.despesas_deputado não tem o mesmo número de linhas de refined.despesas")


# Linha sem par = não é liderança e o id não existe em refined.deputados.
_FROM_SEM_PAR = """
    FROM refined.despesas_deputado d
    LEFT JOIN refined.deputados dep ON dep.id_deputado = d.id_deputado
"""


def taxa_sem_par(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Por ano: linhas, vínculo por método, liderança e linhas sem par de deputado."""
    return con.execute(
        f"""
        SELECT
            d.ano_arquivo,
            count(*)                                                                AS linhas,
            count(*) FILTER (WHERE d.metodo_vinculo = 'ide_cadastro')               AS por_ide_cadastro,
            count(*) FILTER (WHERE d.metodo_vinculo IN ('votos', 'cadastro_unico')) AS por_reserva,
            count(*) FILTER (WHERE d.eh_lideranca)                                  AS lideranca,
            count(*) FILTER (WHERE NOT d.eh_lideranca AND dep.id_deputado IS NULL)  AS sem_par_deputado
        {_FROM_SEM_PAR}
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()


def ids_sem_par(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Ids de deputado sem par (não liderança), com nome, UF e linhas afetadas."""
    return con.execute(
        f"""
        SELECT d.ano_arquivo, d.nu_deputado_id, d.ide_cadastro,
               any_value(d.nome_parlamentar) AS nome, any_value(d.sigla_uf) AS uf, count(*) AS linhas
        {_FROM_SEM_PAR}
        WHERE NOT d.eh_lideranca AND dep.id_deputado IS NULL
        GROUP BY 1, 2, 3
        ORDER BY 1, 6 DESC
        """
    ).fetchall()


def construir_refined_camara(con: duckdb.DuckDBPyConnection) -> dict:
    """Recria as tabelas de deputados, votos, ponte e a view de despesas por deputado."""
    con.execute("CREATE SCHEMA IF NOT EXISTS refined")
    for tabela in TABELAS:
        _executar(con, tabela)
    _conferir(con)
    return {
        "deputados": _contar(con, "SELECT count(*) FROM refined.deputados"),
        "deputados_sem_partido": _contar(con, "SELECT count(*) FROM refined.deputados WHERE partido_atual IS NULL"),
        "votos": _contar(con, "SELECT count(*) FROM refined.votos"),
        "vinculo": con.execute(
            "SELECT metodo_vinculo, count(*) FROM refined.despesas_deputado GROUP BY 1 ORDER BY 1"
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
