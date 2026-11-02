"""Testes da correlação de Spearman (gasto x participação). Dados inventados, DuckDB em memória.

Resultados conhecidos:
- Monotônico crescente: rho = 1. Decrescente: rho = -1.
- Com empate: gasto médio [100, 100, 200, 300] e participação [10, 20, 30, 40].
  Postos de x (com empate médio): [1,5; 1,5; 3; 4]. Postos de y: [1; 2; 3; 4].
  Pearson dos postos: cov = 4,5; var_x = 4,5; var_y = 5. rho = 4,5 / sqrt(4,5 x 5) = 3/sqrt(10) = 0,9486833.
"""

import math

import duckdb
import pytest

from src.marts import _executar


def montar(linhas):
    """linhas: (id, uf, participacao, denominador, votou_art17, gasto_mes_1, gasto_mes_2)"""
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE SCHEMA marts")
    c.execute("CREATE TABLE refined.deputados (id_deputado INTEGER, uf_atual VARCHAR)")
    c.execute("CREATE TABLE marts.participacao_deputado (id_deputado INTEGER, participacao_pct DOUBLE, "
              "denominador INTEGER, votou_artigo_17 BOOLEAN)")
    c.execute("CREATE TABLE marts.gasto_por_deputado_mes (id_deputado INTEGER, ano INTEGER, mes INTEGER, "
              "valor_liquido_total DECIMAL(18,2))")
    for id_, uf, part, den, art, g1, g2 in linhas:
        c.execute("INSERT INTO refined.deputados VALUES (?, ?)", [id_, uf])
        c.execute("INSERT INTO marts.participacao_deputado VALUES (?, ?, ?, ?)", [id_, part, den, art])
        c.execute("INSERT INTO marts.gasto_por_deputado_mes VALUES (?, 2024, 1, ?)", [id_, g1])
        if g2 is not None:
            c.execute("INSERT INTO marts.gasto_por_deputado_mes VALUES (?, 2024, 2, ?)", [id_, g2])
    _executar(c, "correlacao_gasto_participacao")
    return c


def rho(c, recorte):
    return c.execute("SELECT n, spearman_rho FROM marts.correlacao_gasto_participacao WHERE recorte = ?",
                     [recorte]).fetchone()


def rho_nan_free(c, recorte):
    n, r = rho(c, recorte)
    assert r is None or not math.isnan(r)
    return n, r


def test_monotono_crescente_da_rho_1():
    c = montar([(i, "SP", 10.0 * i, 100, False, 100 * i, None) for i in range(1, 6)])
    n, r = rho(c, "todos")
    assert n == 5 and r == pytest.approx(1.0)


def test_monotono_decrescente_da_rho_menos_1():
    c = montar([(i, "SP", 10.0 * i, 100, False, 1000 - 100 * i, None) for i in range(1, 6)])
    assert rho(c, "todos")[1] == pytest.approx(-1.0)


def test_empate_no_gasto_segue_a_formula_com_postos_medios():
    c = montar([
        (1, "SP", 10.0, 100, False, 100, None),
        (2, "SP", 20.0, 100, False, 100, None),
        (3, "SP", 30.0, 100, False, 200, None),
        (4, "SP", 40.0, 100, False, 300, None),
    ])
    n, r = rho(c, "todos")
    assert n == 4
    assert r == pytest.approx(3 / math.sqrt(10), abs=1e-9)  # 0,9486833


def test_deputado_com_menos_de_30_votacoes_fica_fora():
    c = montar([
        (1, "SP", 10.0, 100, False, 100, None),
        (2, "SP", 20.0, 100, False, 200, None),
        (3, "SP", 30.0, 100, False, 300, None),
        (4, "SP", 40.0, 29, False, 400, None),  # abaixo do mínimo: fora
    ])
    assert rho(c, "todos")[0] == 3


def test_recorte_sem_votou_artigo_17_remove_quem_votou():
    c = montar([
        (1, "SP", 10.0, 100, False, 100, None),
        (2, "SP", 20.0, 100, False, 200, None),
        (3, "SP", 30.0, 100, True, 300, None),   # votou Artigo 17
        (4, "SP", 40.0, 100, False, 400, None),
    ])
    assert rho(c, "todos")[0] == 4
    assert rho(c, "sem votou_artigo_17")[0] == 3


def test_recorte_por_macrorregiao_tem_n_proprio():
    c = montar([
        (1, "SP", 10.0, 100, False, 100, None),
        (2, "RJ", 20.0, 100, False, 200, None),
        (3, "AM", 30.0, 100, False, 300, None),
        (4, "BA", 40.0, 100, False, 400, None),
        (5, "RS", 50.0, 100, False, 500, None),
    ])
    assert rho(c, "macro: Sudeste")[0] == 2
    assert rho(c, "macro: Norte")[0] == 1
    assert rho(c, "macro: Nordeste")[0] == 1
    assert rho(c, "macro: Sul")[0] == 1
    assert rho(c, "macro: Centro-Oeste")[0] == 0 and rho(c, "macro: Centro-Oeste")[1] is None


def test_rho_com_menos_de_tres_pontos_e_nulo_e_nao_nan():
    c = montar([(1, "SP", 10.0, 100, False, 100, None)])
    assert rho(c, "macro: Sudeste") == (1, None)
    assert rho(c, "todos") == (1, None)
