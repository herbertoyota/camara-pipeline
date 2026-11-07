
import streamlit as st
import plotly.express as px

from db import run_query


st.set_page_config(
    page_title="Câmara Analytics",
    page_icon="🏛️",
    layout="wide"
)


# Configuração visual
st.title("🏛️ Câmara Analytics")

st.caption(
    "Análise de despesas parlamentares | 2023–2025"
)


# Dados anuais
df = run_query("""
    SELECT
        ano,
        linhas,
        valor_liquido_total,
        deputados_com_despesa,
        gasto_medio_por_deputado,
        media_mensal_por_deputado
    FROM camara.marts.gasto_resumo_ano
    ORDER BY ano
""")


if df.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()


# Filtro de ano
anos = sorted(df["ano"].tolist(), reverse=True)

ano_selecionado = st.sidebar.selectbox(
    "Ano de referência",
    anos
)

dados_ano = df[
    df["ano"] == ano_selecionado
].iloc[0]


# Formatação monetária
def moeda(valor):
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# Indicadores
st.subheader(f"Indicadores — {ano_selecionado}")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Despesas totais",
    moeda(dados_ano["valor_liquido_total"])
)

col2.metric(
    "Deputados",
    f'{int(dados_ano["deputados_com_despesa"]):,}'
)

col3.metric(
    "Média por deputado",
    moeda(dados_ano["gasto_medio_por_deputado"])
)

col4.metric(
    "Lançamentos",
    f'{int(dados_ano["linhas"]):,}'
)


st.divider()


# Evolução anual
st.subheader("Evolução das despesas")

fig = px.bar(
    df,
    x="ano",
    y="valor_liquido_total",
    text="valor_liquido_total",
    labels={
        "ano": "Ano",
        "valor_liquido_total": "Despesas (R$)"
    }
)

fig.update_traces(
    texttemplate="R$ %{y:,.2s}",
    textposition="outside"
)

fig.update_layout(
    xaxis_title=None,
    yaxis_title="Valor (R$)",
    showlegend=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# Resumo anual
st.subheader("Resumo histórico")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
