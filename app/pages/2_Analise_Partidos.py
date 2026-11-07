
import streamlit as st
import plotly.express as px

from db import run_query


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Análise por Partidos",
    page_icon="🏛️",
    layout="wide"
)

st.title("Análise por Partidos")
st.caption(
    "Comparação das despesas parlamentares entre partidos"
)


# ============================================================
# PALETA VISUAL
# ============================================================

AZUL = "#527A91"

PALETA = [
    "#527A91",
    "#7895A5",
    "#A3B5BD",
    "#657D75",
    "#91A397",
    "#B5AA91",
    "#C6BCA9",
    "#8C8790",
    "#A5A1A8",
    "#6E8494"
]


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================

@st.cache_data(ttl=600)
def carregar_dados():

    df = run_query("""
        SELECT *
        FROM camara.marts.gasto_por_partido_ano
        ORDER BY ano, valor_liquido_total DESC
    """)

    mensal = run_query("""
        SELECT *
        FROM camara.marts.gasto_por_partido_mes
        ORDER BY ano, mes
    """)

    return df, mensal


try:

    df, mensal = carregar_dados()

except Exception as erro:

    st.error(f"Erro ao carregar os dados: {erro}")
    st.stop()


# ============================================================
# TRATAMENTO
# ============================================================

df["ano"] = df["ano"].astype(int)

df["valor_liquido_total"] = (
    df["valor_liquido_total"].fillna(0)
)

df["deputados_com_despesa"] = (
    df["deputados_com_despesa"].fillna(0)
)

mensal["ano"] = mensal["ano"].astype(int)

mensal["mes"] = mensal["mes"].astype(int)

mensal["valor_liquido_total"] = (
    mensal["valor_liquido_total"].fillna(0)
)


# ============================================================
# FILTROS
# ============================================================

st.sidebar.header("Filtros")

anos = sorted(
    df["ano"].unique(),
    reverse=True
)

ano = st.sidebar.selectbox(
    "Ano de referência",
    anos
)

dados = df[
    df["ano"] == ano
].copy()

dados = dados.sort_values(
    "valor_liquido_total",
    ascending=False
)


# ============================================================
# INDICADORES PRINCIPAIS
# ============================================================

st.subheader("Visão geral")

total_gastos = dados["valor_liquido_total"].sum()

total_partidos = dados["partido"].nunique()

total_deputados = int(
    dados["deputados_com_despesa"].sum()
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Despesas totais",
    f"R$ {total_gastos / 1e6:.2f} mi"
)

col2.metric(
    "Partidos analisados",
    f"{total_partidos}"
)

col3.metric(
    "Deputados com despesas",
    f"{total_deputados:,}".replace(",", ".")
)

st.divider()


# ============================================================
# GRÁFICOS PRINCIPAIS
# ============================================================

col1, col2 = st.columns(
    [1.15, 1]
)


# ============================================================
# GRÁFICO 1 - DESPESAS POR PARTIDO
# ============================================================

with col1:

    st.subheader("Despesas por partido")

    dados_barra = (
        dados
        .head(15)
        .sort_values(
            "valor_liquido_total",
            ascending=True
        )
    )

    fig_barra = px.bar(

        dados_barra,

        x="valor_liquido_total",

        y="partido",

        orientation="h",

        text="valor_liquido_total",

        labels={
            "valor_liquido_total": "Despesas (R$)",
            "partido": "Partido"
        },

        color_discrete_sequence=[AZUL]

    )

    fig_barra.update_traces(

        marker_line_width=0,

        texttemplate="R$ %{x:.2s}",

        textposition="outside",

        hovertemplate=(
            "<b>%{y}</b><br>"
            "Despesas: R$ %{x:,.2f}"
            "<extra></extra>"
        )

    )

    fig_barra.update_layout(

        showlegend=False,

        height=470,

        plot_bgcolor="white",

        paper_bgcolor="white",

        xaxis=dict(
            title="Despesas (R$)",
            showgrid=True,
            gridcolor="#EAECEF",
            tickprefix="R$ ",
            tickformat="~s"
        ),

        yaxis=dict(
            title=None,
            showgrid=False
        ),

        margin=dict(
            l=10,
            r=45,
            t=25,
            b=45
        )

    )

    st.plotly_chart(
        fig_barra,
        use_container_width=True
    )


# ============================================================
# GRÁFICO 2 - PARTICIPAÇÃO NOS GASTOS
# ============================================================

with col2:

    st.subheader("Participação nos gastos")

    dados_rosca = (
        dados
        .head(10)
        .copy()
    )

    fig_rosca = px.pie(

        dados_rosca,

        names="partido",

        values="valor_liquido_total",

        hole=0.55,

        color_discrete_sequence=PALETA,

        labels={
            "partido": "Partido",
            "valor_liquido_total": "Despesas"
        }

    )

    fig_rosca.update_traces(

        textposition="inside",

        textinfo="percent",

        textfont=dict(
            size=11,
            color="white"
        ),

        marker=dict(
            line=dict(
                color="white",
                width=2
            )
        ),

        hovertemplate=(
            "<b>%{label}</b><br>"
            "Despesas: R$ %{value:,.2f}<br>"
            "Participação: %{percent}"
            "<extra></extra>"
        )

    )

    fig_rosca.update_layout(

        height=470,

        legend=dict(

            orientation="h",

            yanchor="bottom",

            y=1.12,

            xanchor="center",

            x=0.5,

            font=dict(size=10),

            title=None

        ),

        margin=dict(
            t=110,
            b=20,
            l=20,
            r=20
        ),

        plot_bgcolor="white",

        paper_bgcolor="white"

    )

    st.plotly_chart(
        fig_rosca,
        use_container_width=True
    )


st.divider()


# ============================================================
# EVOLUÇÃO MENSAL POR PARTIDO
# ============================================================

st.subheader("Evolução mensal por partido")

partidos = sorted(
    dados["partido"].dropna().unique()
)

partido_selecionado = st.selectbox(
    "Selecione um partido",
    partidos
)

serie = mensal[
    (mensal["ano"] == ano)
    &
    (mensal["partido"] == partido_selecionado)
].copy()

serie = serie.sort_values("mes")


if not serie.empty:

    fig_linha = px.line(

        serie,

        x="mes",

        y="valor_liquido_total",

        markers=True,

        color_discrete_sequence=[AZUL],

        labels={
            "mes": "Mês",
            "valor_liquido_total": "Despesas (R$)"
        }

    )

    fig_linha.update_traces(

        line=dict(
            width=3
        ),

        marker=dict(
            size=8
        ),

        hovertemplate=(
            "Mês: %{x}<br>"
            "Despesas: R$ %{y:,.2f}"
            "<extra></extra>"
        )

    )

    fig_linha.update_layout(

        height=400,

        showlegend=False,

        plot_bgcolor="white",

        paper_bgcolor="white",

        xaxis=dict(
            title="Mês",
            tickmode="linear",
            dtick=1,
            showgrid=False
        ),

        yaxis=dict(
            title="Despesas (R$)",
            tickprefix="R$ ",
            tickformat="~s",
            showgrid=True,
            gridcolor="#EAECEF"
        ),

        margin=dict(
            l=20,
            r=20,
            t=30,
            b=40
        )

    )

    st.plotly_chart(
        fig_linha,
        use_container_width=True
    )

else:

    st.info(
        "Não existem registros mensais para esse partido e ano."
    )


# ============================================================
# DETALHAMENTO
# ============================================================

st.divider()

st.subheader("Detalhamento por partido")

st.caption(
    f"Despesas parlamentares registradas em {ano}"
)

dados_exibicao = dados.sort_values(
    "valor_liquido_total",
    ascending=False
)

st.dataframe(

    dados_exibicao.style.format({

        "valor_liquido_total": "R$ {:,.2f}",

    }),

    use_container_width=True,

    hide_index=True,

    height=500

)


# ============================================================
# EXPORTAÇÃO
# ============================================================

csv = dados_exibicao.to_csv(
    index=False,
    sep=";",
    decimal=","
).encode("utf-8-sig")

st.download_button(

    label="📥 Exportar dados em CSV",

    data=csv,

    file_name=f"despesas_partidos_{ano}.csv",

    mime="text/csv"

)


# ============================================================
# METODOLOGIA
# ============================================================

with st.expander("Sobre os dados e a metodologia"):

    st.markdown("""
    **Fonte:** Câmara dos Deputados.

    **Período:** ano selecionado no filtro.

    **Despesas totais:** soma dos valores líquidos
    registrados para cada partido.

    **Deputados com despesas:** quantidade de deputados
    identificados com registros de despesas.

    **Participação nos gastos:** proporção das despesas
    de cada partido em relação ao total dos partidos
    apresentados no gráfico.

    **Evolução mensal:** acompanhamento das despesas
    registradas ao longo dos meses.

    Os valores representam despesas parlamentares
    vinculadas aos deputados, não gastos administrativos
    dos diretórios partidários.
    """)
