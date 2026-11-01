"""Limpeza das despesas: raw -> refined.despesas.

A regra de limpeza fica em sql/refined/despesas.sql, uma única implementação em
operações de conjunto. Este módulo:

- lê o salt do hash de CPF da variável de ambiente CAMARA_SALT (falha se faltar);
- executa o SQL;
- confere que nenhuma conversão de valor ou data perdeu dado em silêncio.

Nunca grave o salt em arquivo versionado.
"""

import os
from pathlib import Path

import duckdb

PROJETO = Path(__file__).resolve().parent.parent
DB_PATH = PROJETO / "data" / "camara.duckdb"
SQL_DESPESAS = PROJETO / "sql" / "refined" / "despesas.sql"

VAR_SALT = "CAMARA_SALT"
ANOS = (2023, 2024, 2025)

# (coluna do raw, coluna do refined) convertidas com TRY_CAST. Se o raw tem texto
# e o refined ficou NULL, a conversão falhou.
CONVERSOES = [
    ("numAno", "ano_exercicio"),
    ("numMes", "mes"),
    ("nuDeputadoId", "nu_deputado_id"),
    ("ideCadastro", "ide_cadastro"),
    ("numParcela", "num_parcela"),
    ("numLote", "num_lote"),
    ("numRessarcimento", "num_ressarcimento"),
    ("vlrDocumento", "valor_documento"),
    ("vlrGlosa", "valor_glosa"),
    ("vlrLiquido", "valor_liquido"),
    ("vlrRestituicao", "valor_restituicao"),
    ("datEmissao", "data_emissao"),
    ("datPagamentoRestituicao", "data_pagamento_restituicao"),
]


def ler_salt(ambiente=None) -> str:
    """Devolve o salt de CAMARA_SALT. Falha com mensagem clara se não estiver definido."""
    ambiente = os.environ if ambiente is None else ambiente
    salt = ambiente.get(VAR_SALT, "")
    if not salt.strip():
        raise RuntimeError(
            f"Defina a variável de ambiente {VAR_SALT} antes de rodar a limpeza "
            "(ex.: PowerShell: $env:CAMARA_SALT = '...'). Ver README, seção 'Salt do hash de CPF'."
        )
    return salt


def _conferir_conversoes(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Confere que cada conversão preservou os valores não-vazios.

    Devolve {coluna_refined: linhas_perdidas} e falha se algum número for > 0.
    """
    total_refined = con.execute("SELECT count(*) FROM refined.despesas").fetchone()[0]
    total_raw = sum(con.execute(f"SELECT count(*) FROM raw.ceap_{ano}").fetchone()[0] for ano in ANOS)
    if total_refined != total_raw:
        raise RuntimeError(f"refined tem {total_refined} linhas, raw tem {total_raw}")

    perdidas = {}
    for col_raw, col_ref in CONVERSOES:
        nao_vazios = sum(
            con.execute(f'SELECT count(*) FROM raw.ceap_{ano} WHERE trim("{col_raw}") <> \'\'').fetchone()[0]
            for ano in ANOS
        )
        nao_nulos = con.execute(f"SELECT count({col_ref}) FROM refined.despesas").fetchone()[0]
        perdidas[col_ref] = nao_vazios - nao_nulos
    ruins = {col: n for col, n in perdidas.items() if n}
    if ruins:
        raise RuntimeError(f"Conversões que perderam valores (deveria ser zero): {ruins}")
    return perdidas


def construir_refined(con: duckdb.DuckDBPyConnection, salt: str) -> dict:
    """Recria refined.despesas a partir do raw e devolve os números de conferência."""
    if not salt.strip():
        raise RuntimeError("salt vazio")
    con.execute("CREATE SCHEMA IF NOT EXISTS refined")
    con.execute(SQL_DESPESAS.read_text(encoding="utf-8"), {"salt": salt})
    perdidas = _conferir_conversoes(con)

    return {
        "linhas_por_ano": dict(
            con.execute(
                "SELECT ano_arquivo, count(*) FROM refined.despesas GROUP BY 1 ORDER BY 1"
            ).fetchall()
        ),
        "perdidas_na_conversao": perdidas,
        "datas_suspeitas": con.execute(
            "SELECT count(*) FROM refined.despesas WHERE data_emissao_suspeita"
        ).fetchone()[0],
        "estornos": con.execute("SELECT count(*) FROM refined.despesas WHERE eh_estorno").fetchone()[0],
        "liquido_diverge": con.execute(
            "SELECT count(*) FROM refined.despesas WHERE liquido_diverge"
        ).fetchone()[0],
        "id_documento_nulo": con.execute(
            "SELECT count(*) FROM refined.despesas WHERE id_documento IS NULL"
        ).fetchone()[0],
    }


def carregar_refined(db_path: Path = DB_PATH) -> dict:
    """Lê o salt do ambiente e constrói o refined no banco local."""
    salt = ler_salt()
    with duckdb.connect(str(db_path)) as con:
        return construir_refined(con, salt)


if __name__ == "__main__":
    print(carregar_refined())
