"""Testes da participação em votações (pergunta 4). Dados inventados, DuckDB em memória.

Votações nominais: V1 (10/jan), V2 (10/fev), V3 (10/mar), V4 (10/abr), todas de 2024.
- A: Sim, Não, Artigo 17, Sim. Janela V1..V4. Denominador = 4 - 1 (Art. 17) = 3. Numerador = 3. Participação 100%.
- B: Sim, (ausente em V2), tipo vazio em V3, Abstenção. Janela V1..V4. Denominador = 4 - 1 (vazio) = 3,
  ausência em V2 conta. Numerador = 2. Participação 66,7%.
- C: só Obstrução em V2. Janela V2..V2. Denominador 1, numerador 1. Participação 100%.
- E: só Artigo 17 em V1. Denominador 0 -> participação NULL.
- D: nenhum voto -> não aparece no mart (sem voto no período = NULL).
"""

import duckdb
import pytest

from src.marts import _executar


def votos(con, linhas):
    for id_deputado, id_votacao, data, tipo in linhas:
        con.execute("INSERT INTO refined.votos VALUES (?, ?, ?, ?)", [id_votacao, id_deputado, tipo, data])


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE TABLE refined.votos (id_votacao VARCHAR, id_deputado INTEGER, tipo_voto VARCHAR, data_votacao DATE)")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, nome_parlamentar VARCHAR, "
              "legislatura_inicial INTEGER, legislatura_final INTEGER, partido_atual VARCHAR, uf_atual VARCHAR, "
              "origem_partido_uf VARCHAR)")
    c.execute("INSERT INTO refined.deputados VALUES (1,'A',57,57,NULL,NULL,NULL),(2,'B',57,57,NULL,NULL,NULL),"
              "(3,'C',57,57,NULL,NULL,NULL),(4,'D',57,57,NULL,NULL,NULL),(5,'E',57,57,NULL,NULL,NULL)")
    from datetime import date
    d = {"V1": date(2024, 1, 10), "V2": date(2024, 2, 10), "V3": date(2024, 3, 10), "V4": date(2024, 4, 10)}
    votos(c, [
        (1, "V1", d["V1"], "Sim"), (1, "V2", d["V2"], "Não"), (1, "V3", d["V3"], "Artigo 17"), (1, "V4", d["V4"], "Sim"),
        (2, "V1", d["V1"], "Sim"), (2, "V3", d["V3"], None), (2, "V4", d["V4"], "Abstenção"),
        (3, "V2", d["V2"], "Obstrução"),
        (5, "V1", d["V1"], "Artigo 17"),
    ])
    # Na janela de C (só V2), nenhuma outra votação; V3 e V4 existem como nominais por outros deputados.
    votos(c, [(9, "V3", d["V3"], "Sim"), (9, "V4", d["V4"], "Sim")])
    c.execute("CREATE SCHEMA marts")
    _executar(c, "participacao_deputado")
    yield c
    c.close()


def part(con, id_deputado):
    return con.execute(
        "SELECT votos_registrados, denominador, participacao_pct FROM marts.participacao_deputado WHERE id_deputado = ?",
        [id_deputado]).fetchone()


def test_artigo_17_fica_fora_do_numerador_e_do_denominador(con):
    registrados, denominador, pct = part(con, 1)
    assert (registrados, denominador) == (3, 3)
    assert float(pct) == pytest.approx(100.0)


def test_ausencia_conta_no_denominador_e_tipo_vazio_sai(con):
    registrados, denominador, pct = part(con, 2)
    assert (registrados, denominador) == (2, 3)
    assert float(pct) == pytest.approx(200.0 / 3)


def test_janela_do_proxy_vai_do_primeiro_ao_ultimo_voto(con):
    assert part(con, 3)[1] == 1  # só V2 na janela
    assert float(part(con, 3)[2]) == pytest.approx(100.0)


def test_denominador_zero_da_participacao_nula(con):
    registrados, denominador, pct = part(con, 5)
    assert denominador == 0 and pct is None


def test_deputado_sem_voto_nao_aparece_no_mart(con):
    assert con.execute("SELECT count(*) FROM marts.participacao_deputado WHERE id_deputado = 4").fetchone()[0] == 0


def test_participacao_nunca_passa_de_100(con):
    assert con.execute("SELECT count(*) FROM marts.participacao_deputado WHERE participacao_pct > 100").fetchone()[0] == 0
