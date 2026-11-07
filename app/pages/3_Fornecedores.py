
import streamlit as st
import plotly.express as px

from db import run_query

st.set_page_config(page_title="Fornecedores", page_icon="🏢", layout="wide")

st.title("Análise de Fornecedores")
st.caption("Concentração e distribuição das despesas por fornecedor")

periodos = run_query("""
    SELECT DISTINCT periodo
    FROM camara.marts.gasto_por_fornecedor
    ORDER BY periodo
""")["periodo"].tolist()

if not periodos:
    st.warning("Nenhum período encontrado.")
    st.stop()

periodo = st.sidebar.selectbox("Período", periodos)

df = run_query("""
    SELECT *
    FROM camara.marts.gasto_por_fornecedor
    WHERE periodo = ?
    ORDER BY valor_liquido_total DESC
""", [periodo])

concentracao = run_query("""
    SELECT *
    FROM camara.marts.concentracao_fornecedores
    WHERE periodo = ?
""", [periodo])

top = run_query("""
    SELECT *
    FROM camara.marts.top_fornecedores
    WHERE periodo = ?
    ORDER BY posicao
    LIMIT 10
""", [periodo])

if df.empty:
    st.warning("Não existem fornecedores nesse período.")
    st.stop()

c1, c2, c3 = st.columns(3)

c1.metric(
    "Despesas com fornecedores",
    f"R$ {df['valor_liquido_total'].sum()/1e6:.2f} mi"
)

c2.metric(
    "Fornecedores",
    f"{len(df):,}"
)

if not concentracao.empty:
    r = concentracao.iloc[0]

    c3.metric(
        "Participação do Top 10",
        f"{r['participacao_top10_pct']:.2f}%"
    )

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 10 fornecedores")

    fig = px.bar(
        top.sort_values("valor_liquido_total"),
        x="valor_liquido_total",
        y="fornecedor_nome",
        orientation="h",
        hover_data=["participacao_pct", "linhas"],
        labels={
            "valor_liquido_total": "Despesas (R$)",
            "fornecedor_nome": "Fornecedor"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Concentração dos gastos")

    if not concentracao.empty:
        r = concentracao.iloc[0]

        fig = px.bar(
            x=["Top 10 fornecedores", "Demais fornecedores"],
            y=[
                r["participacao_top10_pct"],
                100 - r["participacao_top10_pct"]
            ],
            labels={"x": "Grupo", "y": "Participação (%)"},
            text_auto=".2f"
        )

        st.plotly_chart(fig, use_container_width=True)

if not concentracao.empty:
    st.subheader("Indicadores de concentração")

    r = concentracao.iloc[0]

    a, b, c = st.columns(3)

    a.metric("Índice HHI", f"{r['hhi']:,.0f}")
    b.metric("Participação Top 10 por raiz", f"{r['participacao_top10_raiz_pct']:.2f}%")
    c.metric("Quantidade de fornecedores", f"{int(r['fornecedores']):,}")

st.divider()

st.subheader("Detalhamento dos fornecedores")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
