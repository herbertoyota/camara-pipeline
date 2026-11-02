"""Valida que o runner dá o mesmo resultado em execuções seguidas.

Roda src.run_pipeline (sem download) duas vezes, cada uma num DuckDB novo em pasta temporária,
e compara todas as tabelas de raw, refined e marts:
- colunas DOUBLE: diferença absoluta até 1e-6;
- as demais colunas (DECIMAL, inteiros, datas, texto): igualdade exata.

Sai com código 1 se houver qualquer diferença. Não toca em data/camara.duckdb.
Não reduz threads: a variação entre execuções precisa aparecer aqui, não ser escondida.

Ordem das linhas: as tabelas são ordenadas pelas colunas que não são DOUBLE. Se duas linhas
tiverem essas colunas iguais, a comparação pode se desalinhar; isso aparece como diferença.

Uso:
    python -m src.validar_runner

Se CAMARA_SALT não estiver definida, usa um salt aleatório só para esta validação (as duas
execuções usam o mesmo). Ele não é gravado em lugar nenhum.
"""

import os
import secrets
import sys
import tempfile
from pathlib import Path

import duckdb

from src import run_pipeline

TOLERANCIA_DOUBLE = 1e-6
SCHEMAS = ("raw", "refined", "marts")
MAXIMO_EXEMPLOS = 5


def _tabelas(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    return con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema IN ('raw', 'refined', 'marts') AND table_type = 'BASE TABLE' "
        "ORDER BY table_schema, table_name"
    ).fetchall()


def _colunas(con: duckdb.DuckDBPyConnection, schema: str, tabela: str) -> list[tuple[str, str]]:
    return con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
        [schema, tabela],
    ).fetchall()


def _iguais(tipo: str, a, b) -> bool:
    if a is None or b is None:
        return a is b
    if tipo == "DOUBLE":
        return a == b or abs(a - b) <= TOLERANCIA_DOUBLE
    return a == b


def comparar_tabela(con_a, con_b, schema: str, tabela: str) -> tuple[int, list[str]]:
    """Devolve (número de diferenças, exemplos). Zero diferenças = a tabela bate."""
    nome = f"{schema}.{tabela}"
    colunas = _colunas(con_a, schema, tabela)
    if colunas != _colunas(con_b, schema, tabela):
        return 1, [f"{nome}: colunas ou tipos diferentes"]
    total_a = con_a.execute(f'SELECT count(*) FROM {schema}."{tabela}"').fetchone()[0]
    total_b = con_b.execute(f'SELECT count(*) FROM {schema}."{tabela}"').fetchone()[0]
    if total_a != total_b:
        return 1, [f"{nome}: {total_a} linhas numa execução e {total_b} na outra"]

    nomes = ", ".join(f'"{c}"' for c, _ in colunas)
    chaves = [f'"{c}"' for c, t in colunas if t != "DOUBLE"] or [f'"{c}"' for c, _ in colunas]
    sql = f'SELECT {nomes} FROM {schema}."{tabela}" ORDER BY {", ".join(chaves)}'
    linhas_a = con_a.execute(sql).fetchall()
    linhas_b = con_b.execute(sql).fetchall()
    tipos = [t for _, t in colunas]

    diferencas, exemplos = 0, []
    for i, (la, lb) in enumerate(zip(linhas_a, linhas_b)):
        for j, (va, vb) in enumerate(zip(la, lb)):
            if not _iguais(tipos[j], va, vb):
                diferencas += 1
                if len(exemplos) < MAXIMO_EXEMPLOS:
                    exemplos.append(f"{nome}, linha {i + 1}, coluna {colunas[j][0]}: {va!r} x {vb!r}")
                break
    return diferencas, exemplos


def comparar_bancos(caminho_a: Path, caminho_b: Path) -> dict:
    resultado = {"tabelas": 0, "diferencas": 0, "exemplos": []}
    with duckdb.connect(str(caminho_a), read_only=True) as con_a, \
            duckdb.connect(str(caminho_b), read_only=True) as con_b:
        tabelas_a = _tabelas(con_a)
        if tabelas_a != _tabelas(con_b):
            resultado["diferencas"] += 1
            resultado["exemplos"].append("conjunto de tabelas diferente entre as execuções")
        for schema, tabela in tabelas_a:
            resultado["tabelas"] += 1
            n, exemplos = comparar_tabela(con_a, con_b, schema, tabela)
            resultado["diferencas"] += n
            resultado["exemplos"].extend(exemplos)
    return resultado


def validar() -> dict:
    if not os.environ.get("CAMARA_SALT", "").strip():
        os.environ["CAMARA_SALT"] = secrets.token_hex(32)
    with tempfile.TemporaryDirectory() as pasta:
        a = Path(pasta) / "execucao_a.duckdb"
        b = Path(pasta) / "execucao_b.duckdb"
        run_pipeline.executar(a, baixar=False)
        run_pipeline.executar(b, baixar=False)
        return comparar_bancos(a, b)


def main() -> int:
    resultado = validar()
    print(f"Tabelas comparadas: {resultado['tabelas']}")
    print(f"Diferenças: {resultado['diferencas']}")
    for exemplo in resultado["exemplos"]:
        print(f"  {exemplo}")
    return 0 if resultado["diferencas"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
