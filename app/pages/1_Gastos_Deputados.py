
import streamlit as st
import plotly.express as px

from db import run_query


st.set_page_config(
    page_title="Gastos por Deputado",
    page_icon="👥",
    layout="wide"
)

st.title("Gastos por Deputado")
st.caption("Análise individual das despesas parlamentares")


# Carregar dados
df = run_query("""
    SELECT
        ano,
        id_deputado,
        nome_parlamentar,
        partido,
        uf,
        linhas,
        meses_com_despesa,
        valor_liquido_total,
        valor_convencao_sinal,
        linhas_divergentes
    FROM camara.marts.gasto_por_deputado_ano
""")


if df.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()


# Filtros
st.sidebar.header("Filtros")

anos = sorted(df["ano"].unique(), reverse=True)

ano = st.sidebar.selectbox("Ano", anos)

partidos = sorted(
    df.loc[df["ano"] == ano, "partido"]
    .dropna()
    .unique()
)

partido = st.sidebar.selectbox(
    "Partido",
    ["Todos"] + partidos
)

ufs = sorted(
    df.loc[df["ano"] == ano, "uf"]
    .dropna()
    .unique()
)

uf = st.sidebar.selectbox(
    "Estado",
    ["Todos"] + ufs
)


# Aplicar filtros
filtrado = df[df["ano"] == ano].copy()

if partido != "Todos":
    filtrado = filtrado[
        filtrado["partido"] == partido
    ]

if uf != "Todos":
    filtrado = filtrado[
        filtrado["uf"] == uf
    ]


# Indicadores
def moeda(valor):
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


total = filtrado["valor_liquido_total"].sum()

media = filtrado["valor_liquido_total"].mean()

quantidade = filtrado["id_deputado"].nunique()

col1, col2, col3 = st.columns(3)

col1.metric("Despesas totais", moeda(total))
col2.metric("Média por deputado", moeda(media))
col3.metric("Deputados", f"{quantidade:,}")


st.divider()


# Ranking
st.subheader("Ranking de despesas")

top10 = (
    filtrado
    .nlargest(10, "valor_liquido_total")
    .sort_values("valor_liquido_total")
)

fig = px.bar(
    top10,
    x="valor_liquido_total",
    y="nome_parlamentar",
    color="partido",
    orientation="h",
    hover_data=["uf", "linhas"],
    labels={
        "valor_liquido_total": "Despesas (R$)",
        "nome_parlamentar": "Deputado",
        "partido": "Partido",
        "uf": "Estado",
        "linhas": "Lançamentos"
    },
    title="Top 10 deputados por despesas"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# Tabela detalhada
st.subheader("Detalhamento por deputado")

tabela = filtrado.sort_values(
    "valor_liquido_total",
    ascending=False
)

st.dataframe(
    tabela,
    use_container_width=True,
    hide_index=True,
    column_config={
        "valor_liquido_total": st.column_config.NumberColumn(
            "Despesas totais",
            format="R$ %.2f"
        ),
        "valor_convencao_sinal": st.column_config.NumberColumn(
            "Convenção de sinal",
            format="R$ %.2f"
        )
    }
)
