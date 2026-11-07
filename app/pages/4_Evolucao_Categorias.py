
import streamlit as st
import plotly.express as px

from db import run_query

st.set_page_config(page_title="Evolução", page_icon="📈", layout="wide")

st.title("Evolução das Despesas")
st.caption("Comportamento dos gastos parlamentares ao longo do tempo")

anual = run_query("""
    SELECT *
    FROM camara.marts.gasto_resumo_ano
    ORDER BY ano
""")

categorias = run_query("""
    SELECT *
    FROM camara.marts.crescimento_categorias
    WHERE NOT eh_agregado
    ORDER BY valor_2025 DESC
""")

c1, c2 = st.columns(2)

c1.metric(
    "Despesas em 2023",
    f"R$ {anual.iloc[0]['valor_liquido_total']/1e6:.2f} mi"
)

c2.metric(
    "Despesas em 2025",
    f"R$ {anual.iloc[-1]['valor_liquido_total']/1e6:.2f} mi"
)

st.divider()

st.subheader("Evolução anual")

fig = px.line(
    anual,
    x="ano",
    y="valor_liquido_total",
    markers=True,
    text="valor_liquido_total",
    labels={
        "ano": "Ano",
        "valor_liquido_total": "Despesas (R$)"
    }
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Crescimento por categoria")

metricas = [
    "var_pct_2023_2025",
    "var_pct_2023_2024",
    "var_pct_2024_2025"
]

metrica = st.selectbox(
    "Comparação",
    metricas,
    format_func=lambda x: {
        "var_pct_2023_2025": "2023–2025",
        "var_pct_2023_2024": "2023–2024",
        "var_pct_2024_2025": "2024–2025"
    }[x]
)

validas = categorias.dropna(subset=[metrica]).copy()

top = (
    validas
    .sort_values(metrica, ascending=False)
    .head(15)
)

fig = px.bar(
    top.sort_values(metrica),
    x=metrica,
    y="tipo_despesa",
    orientation="h",
    labels={
        metrica: "Variação (%)",
        "tipo_despesa": "Categoria"
    },
    title="Categorias com maior crescimento percentual"
)

st.plotly_chart(fig, use_container_width=True)

st.subheader("Comparação dos valores por ano")

colunas = [
    "tipo_despesa",
    "valor_2023",
    "valor_2024",
    "valor_2025",
    "var_pct_2023_2025"
]

st.dataframe(
    categorias[colunas],
    use_container_width=True,
    hide_index=True
)
