"""Testes da limpeza de deputados, votos, ponte, view de despesas por deputado e JOIN.

Dados inventados, DuckDB em memória.
"""

from datetime import date

import duckdb
import pytest

from src.clean_camara import _executar, construir_refined_camara, ids_sem_par, taxa_sem_par

CAD = "https://dadosabertos.camara.leg.br/api/v2/deputados/"


def inserir(con, tabela, linhas):
    for linha in linhas:
        colunas = ", ".join(f'"{c}"' for c in linha)
        marcas = ", ".join("?" for _ in linha)
        con.execute(f"INSERT INTO {tabela} ({colunas}) VALUES ({marcas})", list(linha.values()))


def cadastro(id_, nome):
    return {"uri": CAD + str(id_), "nome": nome, "idLegislaturaInicial": "57", "idLegislaturaFinal": "57",
            "nomeCivil": "NOME FICTICIO 4", "cpf": "11122233344", "dataNascimento": "1980-01-01",
            "municipioNascimento": "Recife"}


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA raw")
    c.execute("CREATE TABLE raw.deputados (uri VARCHAR, nome VARCHAR, idLegislaturaInicial VARCHAR, "
              "idLegislaturaFinal VARCHAR, nomeCivil VARCHAR, cpf VARCHAR, dataNascimento VARCHAR, "
              "municipioNascimento VARCHAR)")
    for ano in (2023, 2024, 2025):
        c.execute(f"CREATE TABLE raw.votacoes_{ano} (id VARCHAR, \"data\" VARCHAR, siglaOrgao VARCHAR)")
        c.execute(f"CREATE TABLE raw.votacoes_votos_{ano} (idVotacao VARCHAR, deputado_id VARCHAR, "
                  "deputado_nome VARCHAR, deputado_siglaPartido VARCHAR, deputado_siglaUf VARCHAR, "
                  "dataHoraVoto VARCHAR, voto VARCHAR)")

    inserir(c, "raw.deputados", [
        cadastro(100, "Ana Souza"),
        cadastro(101, "Carlos Gomes"),
        cadastro(102, "Carlos Gomes"),       # homônimo de 101
        cadastro(103, "Zé Único"),           # sem voto; partido vem da despesa
        cadastro(104, "Joaquim Acento"),
        cadastro(105, "Sem Nada"),           # sem voto e com despesa
        cadastro(106, "Ninguém"),            # sem voto e sem despesa
    ])
    inserir(c, "raw.votacoes_2024", [{"id": "V1", "data": "2024-03-10"}])
    inserir(c, "raw.votacoes_2025", [{"id": "V3", "data": "2025-06-01"}])
    inserir(c, "raw.votacoes_votos_2024", [
        {"idVotacao": "V1", "deputado_id": "100", "deputado_nome": "Ana Souza", "deputado_siglaPartido": "ABC",
         "deputado_siglaUf": "SP", "dataHoraVoto": "2024-03-10T10:00:00", "voto": "Sim"},
        {"idVotacao": "V1", "deputado_id": "101", "deputado_nome": "Carlos Gomes", "deputado_siglaPartido": "XYZ",
         "deputado_siglaUf": "RS", "dataHoraVoto": "2024-03-10T10:01:00", "voto": "Não"},
        {"idVotacao": "V1", "deputado_id": "102", "deputado_nome": "Carlos Gomes", "deputado_siglaPartido": "QRS",
         "deputado_siglaUf": "BA", "dataHoraVoto": "2024-03-10T10:02:00", "voto": "Sim"},
        {"idVotacao": "V1", "deputado_id": "104", "deputado_nome": "Joaquim Acento", "deputado_siglaPartido": "MDB",
         "deputado_siglaUf": "MG", "dataHoraVoto": "2024-03-10T10:03:00", "voto": ""},
    ])
    inserir(c, "raw.votacoes_votos_2025", [
        {"idVotacao": "V3", "deputado_id": "100", "deputado_nome": "Ana Souza", "deputado_siglaPartido": "NEW",
         "deputado_siglaUf": "SP", "dataHoraVoto": "2025-06-01T09:00:00", "voto": "Abstenção"},
    ])

    # refined.despesas mínima, com as colunas que as camadas de deputados usam.
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE TABLE refined.despesas (ano_arquivo INTEGER, mes INTEGER, nu_deputado_id INTEGER, "
              "nome_parlamentar VARCHAR, sigla_uf VARCHAR, sigla_partido VARCHAR, ide_cadastro INTEGER, "
              "eh_lideranca BOOLEAN)")
    inserir(c, "refined.despesas", [
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5001, "nome_parlamentar": "Carlos Gomes",
         "sigla_uf": "RS", "sigla_partido": "XYZ", "ide_cadastro": 101, "eh_lideranca": False},
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5002, "nome_parlamentar": "Carlos Gomes",
         "sigla_uf": "BA", "sigla_partido": "QRS", "ide_cadastro": 102, "eh_lideranca": False},
        # Zé Único: duas despesas; a de mês mais recente define o partido.
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5003, "nome_parlamentar": "Zé Único",
         "sigla_uf": "PE", "sigla_partido": "AAA", "ide_cadastro": 103, "eh_lideranca": False},
        {"ano_arquivo": 2024, "mes": 4, "nu_deputado_id": 5003, "nome_parlamentar": "Zé Único",
         "sigla_uf": "PE", "sigla_partido": "PP", "ide_cadastro": 103, "eh_lideranca": False},
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5004, "nome_parlamentar": "LIDERANÇA DO PT",
         "sigla_uf": "NA", "sigla_partido": None, "ide_cadastro": None, "eh_lideranca": True},
        # ide_cadastro que não existe no cadastro: sem par.
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5005, "nome_parlamentar": "Yury do Paredão",
         "sigla_uf": "CE", "sigla_partido": "MDB", "ide_cadastro": 999, "eh_lideranca": False},
        # Sem ide_cadastro, mas deputado: a reserva por votos resolve (linha duplicada de propósito).
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5006, "nome_parlamentar": "Joaquim Acênto",
         "sigla_uf": "MG", "sigla_partido": "MDB", "ide_cadastro": None, "eh_lideranca": False},
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5006, "nome_parlamentar": "Joaquim Acênto",
         "sigla_uf": "MG", "sigla_partido": "MDB", "ide_cadastro": None, "eh_lideranca": False},
        # Sem ide_cadastro e sem nome no cadastro: sem par.
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5007, "nome_parlamentar": "Fulano Inexistente",
         "sigla_uf": "SP", "sigla_partido": "PT", "ide_cadastro": None, "eh_lideranca": False},
        # Deputado sem voto no período: partido vem da despesa.
        {"ano_arquivo": 2024, "mes": 3, "nu_deputado_id": 5008, "nome_parlamentar": "Sem Nada",
         "sigla_uf": "AM", "sigla_partido": "PSD", "ide_cadastro": 105, "eh_lideranca": False},
    ])
    yield c
    c.close()


def dep(con, id_):
    cur = con.execute("SELECT * FROM refined.deputados WHERE id_deputado = ?", [id_])
    nomes = [d[0] for d in cur.description]
    return dict(zip(nomes, cur.fetchone()))


def vinculo(con):
    return {
        r[0]: (r[1], r[2])
        for r in con.execute(
            "SELECT nu_deputado_id, id_deputado, metodo_vinculo FROM refined.despesas_deputado"
        ).fetchall()
    }


def ponte(con):
    return {
        r[0]: (r[1], r[2])
        for r in con.execute("SELECT nu_deputado_id, id_deputado, metodo FROM refined.ponte_deputado_ceap").fetchall()
    }


# --- deputados -------------------------------------------------------------

def test_deputado_id_vem_da_uri_e_legislaturas_sao_inteiros(con):
    construir_refined_camara(con)
    r = dep(con, 100)
    assert (r["id_deputado"], r["nome_parlamentar"], r["legislatura_inicial"], r["legislatura_final"]) == (
        100, "Ana Souza", 57, 57)


def test_partido_do_voto_mais_recente_tem_prioridade(con):
    construir_refined_camara(con)
    r = dep(con, 100)
    assert (r["partido_atual"], r["uf_atual"], r["origem_partido_uf"]) == ("NEW", "SP", "voto")


def test_sem_voto_usa_a_despesa_mais_recente(con):
    construir_refined_camara(con)
    r = dep(con, 103)
    assert (r["partido_atual"], r["origem_partido_uf"]) == ("PP", "despesa")  # mês 4 vence o mês 3
    assert dep(con, 105)["partido_atual"] == "PSD"


def test_sem_voto_e_sem_despesa_fica_nulo(con):
    construir_refined_camara(con)
    r = dep(con, 106)
    assert (r["partido_atual"], r["uf_atual"], r["origem_partido_uf"]) == (None, None, None)


def test_dimensao_nao_tem_dado_pessoal(con):
    construir_refined_camara(con)
    colunas = {r[0] for r in con.execute("DESCRIBE refined.deputados").fetchall()}
    assert not colunas & {"cpf", "nomeCivil", "dataNascimento", "municipioNascimento", "uri"}


# --- votos -----------------------------------------------------------------

def test_tipo_de_voto_vazio_vira_nulo_e_data_e_date(con):
    construir_refined_camara(con)
    assert con.execute(
        "SELECT tipo_voto, data_votacao FROM refined.votos WHERE id_deputado = 104"
    ).fetchone() == (None, date(2024, 3, 10))
    assert con.execute(
        "SELECT tipo_voto FROM refined.votos WHERE id_deputado = 100 AND id_votacao = 'V1'"
    ).fetchone() == ("Sim",)


def test_filtro_de_periodo_exclui_votacao_fora_de_2023_a_2025(con):
    # Votação de 2022 no arquivo de 2024: o SQL deve excluí-la.
    inserir(con, "raw.votacoes_2024", [{"id": "V0", "data": "2022-05-01"}])
    inserir(con, "raw.votacoes_votos_2024", [
        {"idVotacao": "V0", "deputado_id": "100", "deputado_nome": "Ana Souza", "deputado_siglaPartido": "ABC",
         "deputado_siglaUf": "SP", "dataHoraVoto": "2022-05-01T10:00:00", "voto": "Sim"},
    ])
    _executar(con, "votos")
    assert con.execute("SELECT count(*) FROM refined.votos WHERE id_votacao = 'V0'").fetchone()[0] == 0


def test_voto_fora_do_periodo_falha_a_conferencia(con):
    # A conferência não deixa descarte silencioso: o voto some do refined, então a carga falha.
    inserir(con, "raw.votacoes_2024", [{"id": "V0", "data": "2022-05-01"}])
    inserir(con, "raw.votacoes_votos_2024", [
        {"idVotacao": "V0", "deputado_id": "100", "deputado_nome": "Ana Souza", "deputado_siglaPartido": "ABC",
         "deputado_siglaUf": "SP", "dataHoraVoto": "2022-05-01T10:00:00", "voto": "Sim"},
    ])
    with pytest.raises(RuntimeError, match="perdeu votos"):
        construir_refined_camara(con)


# --- ponte (reserva) -------------------------------------------------------

def test_ponte_desambigua_homonimo_pela_uf_do_voto(con):
    construir_refined_camara(con)
    p = ponte(con)
    assert p[5001] == (101, "votos")  # Carlos Gomes RS
    assert p[5002] == (102, "votos")  # Carlos Gomes BA, mesmo nome, outro id


def test_ponte_usa_cadastro_unico_quando_nao_ha_voto(con):
    construir_refined_camara(con)
    assert ponte(con)[5003] == (103, "cadastro_unico")


def test_ponte_ignora_acento(con):
    construir_refined_camara(con)
    assert ponte(con)[5006] == (104, "votos")  # "Acênto" no CEAP, "Acento" no voto


def test_ponte_deixa_sem_par_lideranca_nome_diferente_e_nome_inexistente(con):
    construir_refined_camara(con)
    p = ponte(con)
    assert p[5004] == (None, None)  # liderança, UF NA
    assert p[5005] == (None, None)  # nome Yury do Paredão não bate com o cadastro
    assert p[5007] == (None, None)  # nome que não existe


# --- view de despesas por deputado (chave principal) -----------------------

def test_chave_principal_e_ide_cadastro(con):
    construir_refined_camara(con)
    v = vinculo(con)
    assert v[5001] == (101, "ide_cadastro")
    assert v[5003] == (103, "ide_cadastro")


def test_linha_sem_ide_cadastro_usa_a_reserva(con):
    construir_refined_camara(con)
    assert vinculo(con)[5006] == (104, "votos")


def test_lideranca_fica_sem_id_e_marcada(con):
    construir_refined_camara(con)
    assert vinculo(con)[5004] == (None, None)
    assert con.execute(
        "SELECT eh_lideranca FROM refined.despesas_deputado WHERE nu_deputado_id = 5004"
    ).fetchone()[0] is True


def test_view_tem_o_mesmo_numero_de_linhas_do_refined(con):
    construir_refined_camara(con)
    assert con.execute("SELECT count(*) FROM refined.despesas_deputado").fetchone()[0] == \
        con.execute("SELECT count(*) FROM refined.despesas").fetchone()[0]


# --- JOIN e taxa sem par ---------------------------------------------------

def test_taxa_sem_par_conta_cada_caminho_separado(con):
    construir_refined_camara(con)
    linhas = {r[0]: r for r in taxa_sem_par(con)}
    # 10 linhas: 6 com ide_cadastro (inclui o 999, que não existe no cadastro),
    # 2 pela reserva, 1 liderança e 2 sem par de deputado (999 e o nome inexistente).
    assert linhas[2024] == (2024, 10, 6, 2, 1, 2)


def test_ids_sem_par_lista_o_id_inexistente_e_o_nome_sem_par(con):
    construir_refined_camara(con)
    sem = {(s[1], s[2]) for s in ids_sem_par(con)}
    assert sem == {(5005, 999), (5007, None)}


def test_lideranca_nao_conta_como_sem_par_de_deputado(con):
    construir_refined_camara(con)
    # 5004 é liderança: não aparece na lista de ids sem par.
    assert 5004 not in {s[1] for s in ids_sem_par(con)}


def test_join_com_deputados_so_contabiliza_pares_encontrados(con):
    construir_refined_camara(con)
    total_par = con.execute(
        "SELECT count(*) FROM refined.despesas_deputado d JOIN refined.deputados dep "
        "ON dep.id_deputado = d.id_deputado"
    ).fetchone()[0]
    assert total_par == 7  # 10 linhas, menos 2 sem par e 1 liderança
