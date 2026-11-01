"""Testes da limpeza de deputados, votos, ponte CEAP e JOIN. Dados inventados, DuckDB em memória."""

from datetime import date

import duckdb
import pytest

from src.clean_camara import _executar, construir_refined_camara, ids_sem_par, taxa_sem_par

CAD = "https://dadosabertos.camara.leg.br/api/v2/deputados/"
VOT = "https://dadosabertos.camara.leg.br/api/v2/votacoes/"


def inserir(con, tabela, linhas):
    for linha in linhas:
        colunas = ", ".join(f'"{c}"' for c in linha)
        marcas = ", ".join("?" for _ in linha)
        con.execute(f"INSERT INTO {tabela} ({colunas}) VALUES ({marcas})", list(linha.values()))


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA raw")
    c.execute("CREATE TABLE raw.deputados (uri VARCHAR, nome VARCHAR, idLegislaturaInicial VARCHAR, "
              "idLegislaturaFinal VARCHAR, nomeCivil VARCHAR, cpf VARCHAR, dataNascimento VARCHAR, "
              "municipioNascimento VARCHAR)")
    for ano in (2023, 2024, 2025):
        c.execute(f"CREATE TABLE raw.votacoes_{ano} (id VARCHAR, \"data\" VARCHAR)")
        c.execute(f"CREATE TABLE raw.votacoes_votos_{ano} (idVotacao VARCHAR, deputado_id VARCHAR, "
                  "deputado_nome VARCHAR, deputado_siglaPartido VARCHAR, deputado_siglaUf VARCHAR, "
                  "dataHoraVoto VARCHAR, voto VARCHAR)")

    inserir(c, "raw.deputados", [
        {"uri": CAD + "100", "nome": "Ana Souza", "idLegislaturaInicial": "56", "idLegislaturaFinal": "57",
         "nomeCivil": "NOME FICTICIO 1", "cpf": "11122233344", "dataNascimento": "1980-01-01",
         "municipioNascimento": "Recife"},
        {"uri": CAD + "101", "nome": "Carlos Gomes", "idLegislaturaInicial": "57", "idLegislaturaFinal": "57",
         "nomeCivil": "", "cpf": "", "dataNascimento": "", "municipioNascimento": ""},
        {"uri": CAD + "102", "nome": "Carlos Gomes", "idLegislaturaInicial": "55", "idLegislaturaFinal": "56",
         "nomeCivil": "", "cpf": "", "dataNascimento": "", "municipioNascimento": ""},
        {"uri": CAD + "103", "nome": "Zé Único", "idLegislaturaInicial": "57", "idLegislaturaFinal": "57",
         "nomeCivil": "", "cpf": "", "dataNascimento": "", "municipioNascimento": ""},
        {"uri": CAD + "104", "nome": "Joaquim Acento", "idLegislaturaInicial": "57", "idLegislaturaFinal": "57",
         "nomeCivil": "", "cpf": "", "dataNascimento": "", "municipioNascimento": ""},
    ])
    inserir(c, "raw.votacoes_2024", [
        {"id": "V1", "data": "2024-03-10"},
    ])
    inserir(c, "raw.votacoes_2025", [
        {"id": "V3", "data": "2025-06-01"},
    ])
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

    # refined.despesas mínima: só as colunas que a ponte usa.
    c.execute("CREATE SCHEMA refined")
    c.execute("CREATE TABLE refined.despesas (ano_arquivo INTEGER, nu_deputado_id INTEGER, "
              "nome_parlamentar VARCHAR, sigla_uf VARCHAR)")
    inserir(c, "refined.despesas", [
        {"ano_arquivo": 2024, "nu_deputado_id": 5001, "nome_parlamentar": "Carlos Gomes", "sigla_uf": "RS"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5002, "nome_parlamentar": "Carlos Gomes", "sigla_uf": "BA"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5003, "nome_parlamentar": "Zé Único", "sigla_uf": "PE"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5004, "nome_parlamentar": "LIDERANÇA DO PT", "sigla_uf": "NA"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5005, "nome_parlamentar": "Yury do Paredão", "sigla_uf": "CE"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5006, "nome_parlamentar": "Joaquim Acênto", "sigla_uf": "MG"},
        {"ano_arquivo": 2024, "nu_deputado_id": 5006, "nome_parlamentar": "Joaquim Acênto", "sigla_uf": "MG"},
    ])
    yield c
    c.close()


def ponte(con):
    return {
        r[0]: (r[1], r[2])
        for r in con.execute("SELECT nu_deputado_id, id_deputado, metodo FROM refined.ponte_deputado_ceap").fetchall()
    }


# --- deputados -------------------------------------------------------------

def test_deputado_id_vem_da_uri_e_legislaturas_sao_inteiros(con):
    construir_refined_camara(con)
    r = con.execute("SELECT id_deputado, nome_parlamentar, legislatura_inicial, legislatura_final "
                    "FROM refined.deputados WHERE id_deputado = 100").fetchone()
    assert r == (100, "Ana Souza", 56, 57)


def test_partido_atual_e_o_do_voto_mais_recente(con):
    construir_refined_camara(con)
    partido, uf = con.execute(
        "SELECT partido_atual, uf_atual FROM refined.deputados WHERE id_deputado = 100"
    ).fetchone()
    assert partido == "NEW"  # voto de 2025 é mais recente que o de 2024
    assert uf == "SP"


def test_deputado_sem_voto_fica_sem_partido(con):
    construir_refined_camara(con)
    assert con.execute(
        "SELECT partido_atual, uf_atual FROM refined.deputados WHERE id_deputado = 103"
    ).fetchone() == (None, None)


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
    # Votação de 2022 dentro do arquivo de 2024: o SQL deve excluí-la.
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


# --- ponte CEAP -> API -----------------------------------------------------

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


def test_lideranca_e_nome_diferente_ficam_sem_par(con):
    construir_refined_camara(con)
    p = ponte(con)
    assert p[5004] == (None, None)  # liderança, UF NA
    assert p[5005] == (None, None)  # nome diferente entre fontes (caso Yury)


def test_ponte_nao_duplica_linhas_do_ceap(con):
    construir_refined_camara(con)
    # nu_deputado_id 5006 aparece duas vezes em refined.despesas: a ponte tem uma linha só.
    assert con.execute(
        "SELECT count(*) FROM refined.ponte_deputado_ceap WHERE nu_deputado_id = 5006"
    ).fetchone()[0] == 1


# --- JOIN e ids sem par ---------------------------------------------------

def test_taxa_sem_par_conta_deputado_e_lideranca_separados(con):
    construir_refined_camara(con)
    linhas = {r[0]: r for r in taxa_sem_par(con)}
    ano, total, _por_votos, _por_cad, sem_lider, sem_dep = linhas[2024]
    assert total == 7
    assert sem_dep == 1  # Yury
    assert sem_lider == 1  # liderança


def test_ids_sem_par_lista_o_id_sem_par(con):
    construir_refined_camara(con)
    sem = ids_sem_par(con)
    assert [(s[0], s[1], s[4]) for s in sem] == [(2024, 5005, 1)]


def test_join_so_contabiliza_pares_encontrados(con):
    construir_refined_camara(con)
    total_par = con.execute(
        "SELECT count(*) FROM refined.despesas d JOIN refined.ponte_deputado_ceap p "
        "ON p.ano_arquivo = d.ano_arquivo AND p.nu_deputado_id = d.nu_deputado_id "
        "WHERE p.id_deputado IS NOT NULL"
    ).fetchone()[0]
    assert total_par == 5  # 7 linhas (5006 aparece 2x), menos Yury e liderança
