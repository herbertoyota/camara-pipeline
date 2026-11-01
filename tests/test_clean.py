"""Testes da limpeza raw -> refined. Dados inventados, DuckDB em memória.

O salt é sempre definido por monkeypatch: estes testes nunca leem CAMARA_SALT
do ambiente real.
"""

import hashlib
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from src.clean import ANOS, construir_refined, ler_salt

COLUNAS_RAW = [
    "txNomeParlamentar", "cpf", "ideCadastro", "nuCarteiraParlamentar", "nuLegislatura",
    "sgUF", "sgPartido", "codLegislatura", "numSubCota", "txtDescricao",
    "numEspecificacaoSubCota", "txtDescricaoEspecificacao", "txtFornecedor", "txtCNPJCPF",
    "txtNumero", "indTipoDocumento", "datEmissao", "vlrDocumento", "vlrGlosa", "vlrLiquido",
    "numMes", "numAno", "numParcela", "txtPassageiro", "txtTrecho", "numLote",
    "numRessarcimento", "datPagamentoRestituicao", "vlrRestituicao", "nuDeputadoId",
    "ideDocumento", "urlDocumento",
]

# Valores padrão de uma linha válida. Cada teste sobrescreve o que precisa.
PADRAO = {
    "txNomeParlamentar": "NOME FICTICIO 2", "cpf": "11122233344", "ideCadastro": "1",
    "sgUF": "SP", "sgPartido": "ABC", "txtDescricao": "TELEFONIA",
    "txtFornecedor": "Fornecedor Teste", "txtCNPJCPF": "09.296.295/0001-60",
    "txtNumero": "1", "indTipoDocumento": "0", "datEmissao": "2024-02-18T00:00:00",
    "vlrDocumento": "100", "vlrGlosa": "0", "vlrLiquido": "100", "numMes": "2",
    "numAno": "2024", "numParcela": "1", "numLote": "10", "numRessarcimento": "0",
    "vlrRestituicao": "", "nuDeputadoId": "2000", "ideDocumento": "123",
    "urlDocumento": "http://exemplo", "txtPassageiro": "", "datPagamentoRestituicao": "",
}

SALT_TESTE = "salt-de-teste"


@pytest.fixture
def con(monkeypatch):
    monkeypatch.setenv("CAMARA_SALT", SALT_TESTE)
    conexao = duckdb.connect(":memory:")
    conexao.execute("CREATE SCHEMA raw")
    colunas = ", ".join(f'"{c}" VARCHAR' for c in COLUNAS_RAW)
    for ano in ANOS:
        conexao.execute(f"CREATE TABLE raw.ceap_{ano} ({colunas})")
    yield conexao
    conexao.close()


def inserir(con, ano=2024, **campos):
    valores = {**PADRAO, **campos}
    nomes = ", ".join(f'"{c}"' for c in COLUNAS_RAW)
    marcas = ", ".join("?" for _ in COLUNAS_RAW)
    con.execute(
        f"INSERT INTO raw.ceap_{ano} ({nomes}) VALUES ({marcas})",
        [valores.get(c, "") for c in COLUNAS_RAW],
    )


def linha(con, num_documento):
    cur = con.execute("SELECT * FROM refined.despesas WHERE num_documento = ?", [num_documento])
    nomes = [d[0] for d in cur.description]
    return dict(zip(nomes, cur.fetchone()))


def refinar(con, salt=SALT_TESTE):
    return construir_refined(con, salt)


# --- valores ---------------------------------------------------------------

def test_valor_no_formato_do_dado_real(con):
    inserir(con, txtNumero="v1", vlrDocumento="1682.9", vlrGlosa="", vlrLiquido="1682.9")
    refinar(con)
    r = linha(con, "v1")
    assert r["valor_documento"] == Decimal("1682.90")
    assert r["valor_liquido"] == Decimal("1682.90")
    assert r["valor_glosa"] is None  # vazio vira NULL


def test_valor_negativo_e_zero(con):
    inserir(con, txtNumero="neg", vlrDocumento="-50", vlrGlosa="0", vlrLiquido="-50")
    inserir(con, txtNumero="zero", vlrDocumento="0", vlrGlosa="0", vlrLiquido="0")
    refinar(con)
    assert linha(con, "neg")["valor_documento"] == Decimal("-50.00")
    assert linha(con, "zero")["valor_documento"] == Decimal("0.00")


def test_valor_invalido_falha_a_conferencia(con):
    inserir(con, txtNumero="ruim", vlrDocumento="abc")
    with pytest.raises(RuntimeError, match="valor_documento"):
        refinar(con)


# --- datas -----------------------------------------------------------------

def test_data_valida_e_vazia(con):
    inserir(con, txtNumero="ok", datEmissao="2024-02-18T00:00:00")
    inserir(con, txtNumero="vazia", datEmissao="")
    refinar(con)
    assert linha(con, "ok")["data_emissao"] == date(2024, 2, 18)
    assert linha(con, "ok")["data_emissao_suspeita"] is False
    assert linha(con, "vazia")["data_emissao"] is None


def test_data_invalida_falha_a_conferencia(con):
    inserir(con, txtNumero="ruim", datEmissao="2024-02-30T00:00:00")
    with pytest.raises(RuntimeError, match="data_emissao"):
        refinar(con)


def test_data_fora_da_faixa_e_sinalizada_sem_descartar(con):
    inserir(con, txtNumero="antiga", datEmissao="1999-01-01T00:00:00")
    inserir(con, txtNumero="futura", datEmissao="2099-01-01T00:00:00")
    refinar(con)
    assert linha(con, "antiga")["data_emissao_suspeita"] is True
    assert linha(con, "futura")["data_emissao_suspeita"] is True


# --- fornecedor ------------------------------------------------------------

def test_nome_normalizado(con):
    inserir(con, txtNumero="n1", txtFornecedor="  Claro  NXT   Telecomunicações S.A ")
    inserir(con, txtNumero="n2", txtFornecedor="CORRETORA DE IMÓVEIS LTDA")
    refinar(con)
    assert linha(con, "n1")["fornecedor_nome"] == "CLARO NXT TELECOMUNICACOES S.A"
    assert linha(con, "n2")["fornecedor_nome"] == "CORRETORA DE IMOVEIS LTDA"


def test_nome_de_pessoa_fisica_vira_rotulo(con):
    inserir(con, txtNumero="pf", txtCNPJCPF="444.444.444-44", txtFornecedor="Maria da Silva")
    inserir(con, txtNumero="pj", txtCNPJCPF="09.296.295/0001-60", txtFornecedor="Empresa Ltda")
    refinar(con)
    assert linha(con, "pf")["fornecedor_nome"] == "PESSOA FISICA"
    assert linha(con, "pj")["fornecedor_nome"] == "EMPRESA LTDA"


def test_nome_de_pessoa_fisica_nao_aparece_no_refined(con):
    inserir(con, txtNumero="pf", txtCNPJCPF="444.444.444-44", txtFornecedor="Maria da Silva")
    refinar(con)
    texto = repr(con.execute("SELECT * FROM refined.despesas").fetchall())
    assert "MARIA" not in texto.upper()


def test_nome_com_cpf_no_texto_nao_sai_no_refined(con):
    # CNPJ de empresário individual: o nome traz o CPF do dono.
    inserir(con, txtNumero="mei", txtCNPJCPF="40.691.496/0001-01",
            txtFornecedor="NOME FICTICIO 5 222.222.222-22")
    inserir(con, txtNumero="mei2", txtCNPJCPF="40.691.496/0001-01",
            txtFornecedor="NOME FICTICIO 5 22222222222")
    refinar(con)
    assert linha(con, "mei")["fornecedor_nome"] == "NOME OCULTADO"
    assert linha(con, "mei")["tipo_documento_fornecedor"] == "CNPJ"
    texto = repr(con.execute("SELECT * FROM refined.despesas").fetchall())
    assert "22222222222" not in texto
    assert "222.222.222-22" not in texto
    assert "VILMARA" not in texto


def test_nome_de_pessoa_fisica_em_cnpj_fica_oculto(con):
    # Mesmo nome de uma pessoa física em outra linha, agora com CNPJ.
    inserir(con, txtNumero="pf", txtCNPJCPF="444.444.444-44", txtFornecedor="Maria da Silva")
    inserir(con, txtNumero="pj", txtCNPJCPF="09.296.295/0001-60", txtFornecedor="MARIA DA SILVA")
    inserir(con, txtNumero="outra", txtCNPJCPF="09.296.295/0001-60", txtFornecedor="Empresa Ltda")
    refinar(con)
    assert linha(con, "pj")["fornecedor_nome"] == "NOME OCULTADO"
    assert linha(con, "outra")["fornecedor_nome"] == "EMPRESA LTDA"


def test_numero_do_documento_com_cpf_do_fornecedor_nao_sai(con):
    inserir(con, txtNumero="11111111111", txtCNPJCPF="003.667.080/40  -", txtFornecedor="Fornecedora")
    inserir(con, txtNumero="NF-123", txtCNPJCPF="003.667.080/40  -", txtFornecedor="Fornecedora")
    refinar(con)
    assert linha(con, "NF-123")["num_documento"] == "NF-123"
    texto = repr(con.execute("SELECT * FROM refined.despesas").fetchall())
    assert "11111111111" not in texto


def test_cnpj_sem_cpf_no_nome_mantem_o_nome(con):
    inserir(con, txtNumero="pj", txtCNPJCPF="09.296.295/0001-60",
            txtFornecedor="EMPRESA 12.345.678/0001-99 LTDA")
    refinar(con)
    assert linha(con, "pj")["fornecedor_nome"] == "EMPRESA 12.345.678/0001-99 LTDA".upper()


def test_documento_cnpj_fica_em_claro(con):
    inserir(con, txtNumero="cnpj", txtCNPJCPF="09.296.295/0001-60")
    refinar(con)
    r = linha(con, "cnpj")
    assert r["tipo_documento_fornecedor"] == "CNPJ"
    assert r["documento_fornecedor"] == "09296295000160"


def test_documento_cpf_vira_hash_e_outro_fica_em_claro(con):
    inserir(con, txtNumero="cpf", txtCNPJCPF="444.444.444-44")
    inserir(con, txtNumero="outro", txtCNPJCPF="1234")
    inserir(con, txtNumero="vazio", txtCNPJCPF="")
    refinar(con)
    cpf = linha(con, "cpf")
    assert cpf["tipo_documento_fornecedor"] == "CPF"
    assert cpf["documento_fornecedor"] != "44444444444"
    assert len(cpf["documento_fornecedor"]) == 64  # SHA-256 em hexadecimal
    assert linha(con, "outro")["tipo_documento_fornecedor"] == "OUTRO"
    assert linha(con, "outro")["documento_fornecedor"] == "1234"
    assert linha(con, "vazio")["tipo_documento_fornecedor"] is None


# --- hash de CPF e salt ----------------------------------------------------

def test_hash_cpf_segue_a_formula_com_salt(con):
    inserir(con, txtNumero="cpf", txtCNPJCPF="444.444.444-44")
    refinar(con, salt="sal-A")
    esperado = hashlib.sha256(b"sal-A|44444444444").hexdigest()
    assert linha(con, "cpf")["documento_fornecedor"] == esperado


def test_hash_cpf_deterministico_com_mesmo_salt_e_diferente_com_outro(con):
    inserir(con, txtNumero="cpf", txtCNPJCPF="444.444.444-44")
    refinar(con, salt="sal-A")
    primeiro = linha(con, "cpf")["documento_fornecedor"]
    refinar(con, salt="sal-A")
    assert linha(con, "cpf")["documento_fornecedor"] == primeiro
    refinar(con, salt="sal-B")
    assert linha(con, "cpf")["documento_fornecedor"] != primeiro


def test_cpf_nao_aparece_em_claro_no_refined(con):
    inserir(con, txtNumero="cpf", txtCNPJCPF="444.444.444-44")
    refinar(con)
    texto = repr(con.execute("SELECT * FROM refined.despesas").fetchall())
    assert "44444444444" not in texto
    assert "444.444.444-44" not in texto


def test_sem_salt_falha_com_erro_claro():
    with pytest.raises(RuntimeError, match="CAMARA_SALT"):
        ler_salt({})
    with pytest.raises(RuntimeError, match="CAMARA_SALT"):
        ler_salt({"CAMARA_SALT": "   "})


def test_ler_salt_le_o_valor_informado():
    assert ler_salt({"CAMARA_SALT": "abc"}) == "abc"


# --- estorno, divergência e colunas --------------------------------------

def test_eh_estorno(con):
    inserir(con, txtNumero="doc_neg", vlrDocumento="-100", vlrGlosa="0", vlrLiquido="-100")
    inserir(con, txtNumero="liq_neg", vlrDocumento="100", vlrGlosa="0", vlrLiquido="-5")
    inserir(con, txtNumero="positivo", vlrDocumento="100", vlrGlosa="0", vlrLiquido="100")
    inserir(con, txtNumero="zero", vlrDocumento="0", vlrGlosa="0", vlrLiquido="0")
    refinar(con)
    assert linha(con, "doc_neg")["eh_estorno"] is True
    assert linha(con, "liq_neg")["eh_estorno"] is True
    assert linha(con, "positivo")["eh_estorno"] is False
    assert linha(con, "zero")["eh_estorno"] is False


def test_liquido_diverge(con):
    inserir(con, txtNumero="div", vlrDocumento="600", vlrGlosa="0", vlrLiquido="235.6")
    inserir(con, txtNumero="ok", vlrDocumento="600", vlrGlosa="", vlrLiquido="600")
    refinar(con)
    assert linha(con, "div")["liquido_diverge"] is True
    assert linha(con, "ok")["liquido_diverge"] is False


def test_id_documento_zero_vira_nulo(con):
    inserir(con, txtNumero="zero", ideDocumento="0")
    inserir(con, txtNumero="id", ideDocumento="123")
    refinar(con)
    assert linha(con, "zero")["id_documento"] is None
    assert linha(con, "id")["id_documento"] == 123


def test_pessoais_fora_do_refined(con):
    inserir(con, txtNumero="p", txtPassageiro="FULANO DE TAL")
    inserir(con, txtNumero="q", txtPassageiro="")
    refinar(con)
    colunas = {r[0] for r in con.execute("DESCRIBE refined.despesas").fetchall()}
    assert "cpf" not in colunas
    assert "txtPassageiro" not in colunas
    assert linha(con, "p")["tem_passageiro"] is True
    assert linha(con, "q")["tem_passageiro"] is False


def test_empilha_os_tres_anos(con):
    inserir(con, ano=2023, txtNumero="a")
    inserir(con, ano=2024, txtNumero="b")
    inserir(con, ano=2025, txtNumero="c")
    stats = refinar(con)
    assert stats["linhas_por_ano"] == {2023: 1, 2024: 1, 2025: 1}
    assert linha(con, "c")["ano_arquivo"] == 2025
