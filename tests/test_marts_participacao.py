"""Testes da participação em votações de plenário (pergunta 4). Dados inventados, DuckDB em memória.

Votações de plenário (PLEN): V1 (10/jan), V2 (10/fev), V3 (10/mar), V4 (10/abr), 2024.
Votação de comissão (CCJC): C1 (20/fev), só com o deputado 9.
- A: Sim, Não, Artigo 17, Sim. Janela V1..V4. Denominador = 4 - 1 (Art. 17) = 3. Numerador = 3. 100%.
- B: Sim, (ausente em V2), tipo vazio em V3, Abstenção. Janela V1..V4. Denominador = 4 - 1 = 3
  (a ausência conta). Numerador = 2. 66,7%.
- C: só Obstrução em V2. Janela V2..V2. Denominador 1, numerador 1. 100%.
- E: só Artigo 17 em V1. Denominador 0 -> participação NULL.
- D: nenhum voto -> não aparece no mart.
- Comissão C1 não entra no denominador de plenário de A (ficaria 4 se entrasse), mas aparece em *_todas.
"""

from datetime import date

import duckdb
import pytest

from src.marts import _executar


def votos(con, linhas):
    for id_deputado, id_votacao, data, tipo, orgao in linhas:
        con.execute("INSERT INTO refined.votos VALUES (?, ?, ?, ?, ?)", [id_votacao, id_deputado, tipo, data, orgao])


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE TABLE refined.votos (id_votacao VARCHAR, id_deputado INTEGER, tipo_voto VARCHAR, "
              "data_votacao DATE, sigla_orgao VARCHAR)")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, "
              "legislatura_inicial INTEGER, legislatura_final INTEGER, partido_atual VARCHAR, uf_atual VARCHAR, "
              "origem_partido_uf VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1,'A',57,57,NULL,NULL,NULL),(2,'B',57,57,NULL,NULL,NULL),"
              "(3,'C',57,57,NULL,NULL,NULL),(4,'D',57,57,NULL,NULL,NULL),(5,'E',57,57,NULL,NULL,NULL),"
              "(9,'F',57,57,NULL,NULL,NULL)")
    P = "PLEN"
    d = {"V1": date(2024, 1, 10), "V2": date(2024, 2, 10), "V3": date(2024, 3, 10), "V4": date(2024, 4, 10)}
    votos(c, [
        (1, "V1", d["V1"], "Sim", P), (1, "V2", d["V2"], "Não", P), (1, "V3", d["V3"], "Artigo 17", P), (1, "V4", d["V4"], "Sim", P),
        (2, "V1", d["V1"], "Sim", P), (2, "V3", d["V3"], None, P), (2, "V4", d["V4"], "Abstenção", P),
        (3, "V2", d["V2"], "Obstrução", P),
        (5, "V1", d["V1"], "Artigo 17", P),
        (9, "V3", d["V3"], "Sim", P), (9, "V4", d["V4"], "Sim", P),
        # votação de comissão dentro da janela de A, só com o deputado 9
        (9, "C1", date(2024, 2, 20), "Sim", "CCJC"),
    ])
    c.execute("CREATE SCHEMA marts")
    _executar(c, "participacao_deputado")
    yield c
    c.close()


def part(con, id_deputado):
    return con.execute(
        "SELECT votos_registrados, denominador, participacao_pct, denominador_todas "
        "FROM marts.participacao_deputado WHERE id_deputado = ?", [id_deputado]).fetchone()


def test_artigo_17_fica_fora_do_numerador_e_do_denominador(con):
    registrados, denominador, pct, _ = part(con, 1)
    assert (registrados, denominador) == (3, 3)
    assert float(pct) == pytest.approx(100.0)


def test_ausencia_conta_no_denominador_e_tipo_vazio_sai(con):
    registrados, denominador, pct, _ = part(con, 2)
    assert (registrados, denominador) == (2, 3)
    assert float(pct) == pytest.approx(200.0 / 3)


def test_votacao_de_comissao_nao_entra_no_denominador_de_plenario(con):
    _, denominador, _, denominador_todas = part(con, 1)
    assert denominador == 3          # plenário: V1..V4 menos Art. 17
    assert denominador_todas == 4    # todas: inclui C1 (comparação)


def test_janela_do_proxy_vai_do_primeiro_ao_ultimo_voto_de_plenario(con):
    assert part(con, 3)[1] == 1  # só V2 na janela
    assert float(part(con, 3)[2]) == pytest.approx(100.0)


def test_denominador_zero_da_participacao_nula(con):
    _, denominador, pct, _ = part(con, 5)
    assert denominador == 0 and pct is None


def test_deputado_so_com_comissao_nao_aparece_no_mart(con):
    assert con.execute("SELECT count(*) FROM marts.participacao_deputado WHERE id_deputado = 9").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM marts.participacao_deputado WHERE id_deputado = 4").fetchone()[0] == 0


def test_participacao_nunca_passa_de_100(con):
    assert con.execute("SELECT count(*) FROM marts.participacao_deputado WHERE participacao_pct > 100").fetchone()[0] == 0


def test_votou_artigo_17_e_booleano_por_deputado(con):
    flags = dict(con.execute("SELECT id_deputado, votou_artigo_17 FROM marts.participacao_deputado").fetchall())
    assert flags[1] is True   # A votou Artigo 17 em V3
    assert flags[2] is False  # B tem tipo vazio, não Artigo 17
    assert flags[3] is False
