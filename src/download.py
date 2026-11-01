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


# Arquivos em massa de deputados e votações, publicados sem zip.
# Verificados em 2026-11-01 (HTTP 200 sem User-Agent especial).
URL_DEPUTADOS = "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv"
URL_VOTACOES = "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{ano}.csv"
URL_VOTACOES_VOTOS = "https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{ano}.csv"
ANOS_VOTACOES = (2023, 2024, 2025)


def baixar_csv(url: str, destino: Path, forcar: bool = False) -> Path:
    """Baixa um CSV já pronto, gravando os bytes exatamente como vieram.

    Se o arquivo já existir e `forcar` for False, não baixa de novo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not forcar:
        print(f"Já existe: {destino} (use forcar=True para baixar de novo)")
        return destino

    print(f"Baixando {url} ...")
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(destino, "wb") as f:
            for bloco in resp.iter_content(chunk_size=1024 * 64):
                f.write(bloco)
    print(f"Salvo: {destino} ({destino.stat().st_size:,} bytes)")
    return destino


def baixar_camara(forcar: bool = False) -> list[Path]:
    """Baixa o cadastro de deputados e as votações e votos de 2023 a 2025."""
    arquivos = [baixar_csv(URL_DEPUTADOS, RAW_DIR / "deputados.csv", forcar)]
    for ano in ANOS_VOTACOES:
        arquivos.append(baixar_csv(URL_VOTACOES.format(ano=ano), RAW_DIR / f"votacoes-{ano}.csv", forcar))
        arquivos.append(
            baixar_csv(URL_VOTACOES_VOTOS.format(ano=ano), RAW_DIR / f"votacoesVotos-{ano}.csv", forcar)
        )
    return arquivos


if __name__ == "__main__":
    forcar = "--forcar" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--forcar"]
    if args == ["camara"]:
        baixar_camara(forcar=forcar)
    else:
        anos = args
        if not anos or not all(a.isdigit() for a in anos):
            sys.exit(
                "Uso: python -m src.download <ano> [<ano> ...] [--forcar]   ex.: python -m src.download 2023 2024\n"
                "     python -m src.download camara [--forcar]              (deputados e votos 2023-2025)"
            )
        for ano in anos:
            baixar_ano(int(ano), forcar=forcar)
