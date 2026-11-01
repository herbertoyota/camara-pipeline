"""Carrega os CSVs de data/raw no DuckDB, schema `raw`.

Cada arquivo Ano-{ano}.csv vira a tabela raw.ceap_{ano}. Todas as colunas são
VARCHAR (all_varchar=true): nenhum valor é convertido aqui. Conversão de tipo
começa só no refined.

Re-executável: cada tabela é recriada com CREATE OR REPLACE, então rodar de novo
substitui os dados em vez de acumular linhas.

ATENÇÃO: a coluna `cpf` (do deputado) fica só neste banco local. O banco
(data/*.duckdb) está no .gitignore e nunca vai para o git.
"""

import re
from pathlib import Path

import duckdb

PROJETO = Path(__file__).resolve().parent.parent
RAW_DIR = PROJETO / "data" / "raw"
DB_PATH = PROJETO / "data" / "camara.duckdb"


def nome_tabela(csv_path: Path) -> str:
    """Ano-2025.csv -> raw.ceap_2025."""
    m = re.fullmatch(r"Ano-(\d{4})\.csv", csv_path.name)
    if not m:
        raise ValueError(f"Nome de arquivo inesperado: {csv_path.name}")
    return f"raw.ceap_{m.group(1)}"


def carregar(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Recria a tabela raw do CSV e devolve a contagem de linhas carregadas."""
    tabela = nome_tabela(csv_path)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {tabela} AS
        SELECT * FROM read_csv(
            ?,
            delim=';',
            header=true,
            all_varchar=true,
            sample_size=-1
        )
        """,
        [str(csv_path)],
    )
    return con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]


def carregar_tudo(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> dict[str, int]:
    """Carrega todos os Ano-*.csv de raw_dir. Devolve {tabela: linhas}."""
    csvs = sorted(raw_dir.glob("Ano-*.csv"))
    if not csvs:
        raise FileNotFoundError(f"Nenhum Ano-*.csv em {raw_dir}. Rode: python -m src.download 2025")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    resultado = {}
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for csv_path in csvs:
            linhas = carregar(con, csv_path)
            resultado[nome_tabela(csv_path)] = linhas
            print(f"{nome_tabela(csv_path)}: {linhas:,} linhas (de {csv_path.name})")
    return resultado


if __name__ == "__main__":
    carregar_tudo()
