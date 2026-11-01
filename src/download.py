"""Baixa o arquivo anual de despesas da cota parlamentar (CEAP) para data/raw.

O arquivo é salvo exatamente como veio: o .zip é gravado byte a byte e o CSV
é extraído sem nenhuma conversão de encoding, separador ou conteúdo.
"""

import sys
import zipfile
from pathlib import Path

import requests

# Arquivo em massa publicado pela Câmara (linkado a partir de
# https://dadosabertos.camara.leg.br/cotas/). Verificado em 2026-11-01.
URL_TEMPLATE = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def baixar_ano(ano: int, destino: Path = RAW_DIR, forcar: bool = False) -> Path:
    """Baixa o zip do ano, extrai o CSV e devolve o caminho do CSV.

    Se o CSV já existir e `forcar` for False, não baixa de novo.
    """
    destino.mkdir(parents=True, exist_ok=True)
    csv_path = destino / f"Ano-{ano}.csv"
    if csv_path.exists() and not forcar:
        print(f"Já existe: {csv_path} (use forcar=True para baixar de novo)")
        return csv_path

    url = URL_TEMPLATE.format(ano=ano)
    zip_path = destino / f"Ano-{ano}.csv.zip"
    print(f"Baixando {url} ...")
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for bloco in resp.iter_content(chunk_size=1024 * 64):
                f.write(bloco)

    # Extrai sem transformar: o CSV sai como está dentro do zip.
    with zipfile.ZipFile(zip_path) as zf:
        membros = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if len(membros) != 1:
            raise ValueError(f"Esperava 1 CSV no zip, encontrei: {membros}")
        with zf.open(membros[0]) as origem, open(csv_path, "wb") as saida:
            saida.write(origem.read())

    print(f"Salvo: {csv_path} ({csv_path.stat().st_size:,} bytes)")
    return csv_path


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--forcar"]
    if len(args) != 1 or not args[0].isdigit():
        sys.exit("Uso: python -m src.download <ano> [--forcar]   ex.: python -m src.download 2025")
    baixar_ano(int(args[0]), forcar="--forcar" in sys.argv)
