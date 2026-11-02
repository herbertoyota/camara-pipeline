"""Executa o pipeline inteiro: download (opcional), raw, refined e marts, nesta ordem.

Uso:
    python -m src.run_pipeline                    # baixa o que faltar, carrega tudo
    python -m src.run_pipeline --skip-download    # não toca na rede; usa data/raw como está
    python -m src.run_pipeline --db CAMINHO       # outro arquivo DuckDB (usado na validação)

Re-executável: cada camada é recriada (CREATE OR REPLACE), então rodar de novo não duplica dados.
Exige CAMARA_SALT (salt do hash de CPF); sem ele o pipeline nem começa.
"""

import argparse
import sys
from pathlib import Path

import duckdb

from src import clean, clean_camara, download, load_raw, marts

PROJETO = Path(__file__).resolve().parent.parent
DB_PADRAO = PROJETO / "data" / "camara.duckdb"
ANOS_CEAP = (2023, 2024, 2025)


def executar(db_path: Path, baixar: bool) -> dict:
    salt = clean.ler_salt()  # falha com mensagem clara se CAMARA_SALT não estiver definida
    resumo = {}
    if baixar:
        for ano in ANOS_CEAP:
            download.baixar_ano(ano)
        download.baixar_camara()
    resumo["raw"] = load_raw.carregar_tudo(db_path=db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as con:
        resumo["refined_despesas"] = clean.construir_refined(con, salt)["linhas_por_ano"]
        resumo["refined_camara"] = clean_camara.construir_refined_camara(con)["votos"]
        resumo["marts"] = marts.construir_marts(con)["resumo"]
    return resumo


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline completo: raw, refined e marts.")
    parser.add_argument("--skip-download", action="store_true",
                        help="não baixa nada; usa os arquivos já em data/raw")
    parser.add_argument("--db", type=Path, default=DB_PADRAO, help="arquivo DuckDB de saída")
    args = parser.parse_args(argv)
    try:
        resumo = executar(args.db, baixar=not args.skip_download)
    except RuntimeError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print("Pipeline concluído.")
    print(f"  raw: {resumo['raw']}")
    print(f"  refined.despesas por ano: {resumo['refined_despesas']}")
    print(f"  refined.votos: {resumo['refined_camara']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
