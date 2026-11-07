
import streamlit as st
import plotly.express as px

from db import run_query

st.set_page_config(page_title="Despesas Atípicas", page_icon="🔎", layout="wide")

st.title("Análise de Despesas Atípicas")
st.caption("Exploração de registros sinalizados por critérios estatísticos")

df = run_query("""
    SELECT *
    FROM camara.marts.indicadores_despesa_atipica
""")

if df.empty:
    st.info("Nenhum registro encontrado.")
    st.stop()

anos = sorted(df["ano"].dropna().unique(), reverse=True)

ano = st.sidebar.selectbox("Ano", anos)

dados = df[df["ano"] == ano].copy()

c1, c2, c3 = st.columns(3)

c1.metric("Registros sinalizados", f"{len(dados):,}")

c2.metric(
    "Deputados envolvidos",
    f"{dados['id_deputado'].nunique():,}"
)

c3.metric(
    "Fornecedores envolvidos",
    f"{dados['identificador_fornecedor'].nunique():,}"
)

st.divider()

st.subheader("Distribuição por tipo de despesa")

categoria = (
    dados.groupby("tipo_despesa")
    .size()
    .reset_index(name="quantidade")
    .sort_values("quantidade", ascending=False)
)

fig = px.bar(
    categoria.head(15).sort_values("quantidade"),
    x="quantidade",
    y="tipo_despesa",
    orientation="h",
    labels={
        "quantidade": "Registros",
        "tipo_despesa": "Categoria"
    }
)

st.plotly_chart(fig, use_container_width=True)

st.subheader("Motivos das sinalizações")

motivos = {
    "Acima do P99": "valor_acima_do_p99_da_categoria",
    "Emissão no fim de semana": "emissao_fim_de_semana",
    "Mesmo valor": "mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado",
    "Mesmo fornecedor no mesmo dia": "mesmo_fornecedor_mesmo_dia_mesmo_deputado"
}

contagens = []

for nome, coluna in motivos.items():
    contagens.append({
        "Motivo": nome,
        "Quantidade": int(dados[coluna].sum())
    })

motivos_df = __import__("pandas").DataFrame(contagens)

fig = px.bar(
    motivos_df,
    x="Motivo",
    y="Quantidade",
    text_auto=True
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Registros detalhados")

filtro = st.text_input("Pesquisar deputado")

if filtro:
    dados = dados[
        dados["nome_parlamentar"].str.contains(
            filtro, case=False, na=False
        )
    ]

st.dataframe(
    dados.sort_values(
        "valor_liquido",
        ascending=False
    ),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Uma sinalização estatística não constitui evidência de irregularidade."
)
