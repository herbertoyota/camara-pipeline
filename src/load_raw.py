"""Carrega os CSVs de data/raw no DuckDB, schema `raw`.

Cada arquivo Ano-{ano}.csv vira a tabela raw.ceap_{ano}. Regras do raw:

- Todas as colunas são VARCHAR (all_varchar=true): nenhum valor é convertido.
- Campos vazios ("" no arquivo) ficam como '' e não viram NULL. A sentinela
  em `nullstr` é um texto que não existe no arquivo, então nada vira NULL.
  Quem trata vazio é o refined, com NULLIF(TRIM(col), '').
- Erros de leitura falham a carga. Não há ignore_errors.

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

# Sentinela que não aparece no CSV: impede que "" vire NULL.
SENTINELA_NULL = "\x01SEM_NULL\x01"

# Opções de leitura usadas tanto na carga quanto na contagem de conferência.
OPCOES_LEITURA = f"""
    delim=';',
    header=true,
    all_varchar=true,
    sample_size=-1,
    nullstr='{SENTINELA_NULL}'
"""


def nome_tabela(csv_path: Path) -> str:
    """Ano-2025.csv -> raw.ceap_2025."""
    m = re.fullmatch(r"Ano-(\d{4})\.csv", csv_path.name)
    if not m:
        raise ValueError(f"Nome de arquivo inesperado: {csv_path.name}")
    return f"raw.ceap_{m.group(1)}"


def carregar(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Recria a tabela raw do CSV e devolve a contagem de linhas carregadas.

    A contagem vem do próprio DuckDB lendo o CSV (não de wc -l, porque pode
    haver quebra de linha dentro de campo). Se não bater com a tabela, falha.
    """
    tabela = nome_tabela(csv_path)
    con.execute(
        f"CREATE OR REPLACE TABLE {tabela} AS SELECT * FROM read_csv(?, {OPCOES_LEITURA})",
        [str(csv_path)],
    )
    linhas_tabela = con.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
    linhas_csv = con.execute(
        f"SELECT count(*) FROM read_csv(?, {OPCOES_LEITURA})", [str(csv_path)]
    ).fetchone()[0]
    if linhas_tabela != linhas_csv:
        raise RuntimeError(f"{tabela}: tabela tem {linhas_tabela} linhas, CSV tem {linhas_csv}")

    colunas = [r[0] for r in con.execute(f"DESCRIBE {tabela}").fetchall()]
    condicao = " OR ".join(f'"{c}" IS NULL' for c in colunas)
    nulos = con.execute(f"SELECT count(*) FROM {tabela} WHERE {condicao}").fetchone()[0]
    if nulos:
        raise RuntimeError(f"{tabela}: {nulos} linhas com NULL no raw (deveria ser zero)")
    return linhas_tabela


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
