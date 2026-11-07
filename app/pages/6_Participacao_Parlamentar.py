
from pathlib import Path
import os

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Participação Parlamentar",
    page_icon="🏛️",
    layout="wide"
)

st.title("Participação Parlamentar")
st.caption("Relação entre despesas e participação nas votações | 2023–2025")


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
    "#6E8494",
    "#B1C0C7",
    "#84968C",
    "#D0C8B9",
    "#9CABB2",
    "#747F87"
]


# ============================================================
# CONEXÃO DUCKDB
# ============================================================

@st.cache_resource
def conectar_banco():

    raiz = Path(__file__).resolve().parents[2]

    caminho_env = os.getenv("CAMARA_DB_PATH")

    if caminho_env and Path(caminho_env).exists():
        return duckdb.connect(
            caminho_env,
            read_only=True
        )

    candidatos = []

    pastas = [
        raiz,
        raiz / "data",
        raiz / "data" / "warehouse",
        raiz / "database",
        raiz / "data" / "processed"
    ]

    for pasta in pastas:

        if pasta.exists():
            candidatos.extend(pasta.glob("*.duckdb"))
            candidatos.extend(pasta.glob("*.db"))

    if not candidatos:
        raise FileNotFoundError(
            "Banco DuckDB não encontrado."
        )

    return duckdb.connect(
        str(candidatos[0]),
        read_only=True
    )


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================

@st.cache_data(ttl=600)
def carregar_dados():

    con = conectar_banco()

    # ----------------------------------------
    # PARTICIPAÇÃO DOS DEPUTADOS
    # ----------------------------------------

    query_participacao = """
        WITH gastos AS (

            SELECT
                id_deputado,
                MAX(nome_parlamentar) AS nome_parlamentar,
                arg_max(partido, ano) AS partido,
                arg_max(uf, ano) AS uf,
                SUM(valor_liquido_total) AS gasto_total,
                SUM(linhas) AS total_lancamentos

            FROM marts.gasto_por_deputado_ano

            WHERE ano BETWEEN 2023 AND 2025

            GROUP BY id_deputado
        )

        SELECT
            p.id_deputado,

            COALESCE(
                p.nome_parlamentar,
                g.nome_parlamentar
            ) AS nome_parlamentar,

            g.partido,
            g.uf,

            COALESCE(g.gasto_total, 0) AS gasto_total,

            COALESCE(
                g.total_lancamentos, 0
            ) AS total_lancamentos,

            p.votos_registrados,
            p.votacoes_nominais_periodo,
            p.participacao_pct,
            p.participacao_todas_pct

        FROM marts.participacao_deputado p

        LEFT JOIN gastos g
            ON p.id_deputado = g.id_deputado
    """

    df = con.execute(query_participacao).df()

    # ----------------------------------------
    # DESPESAS POR PARTIDO
    # ----------------------------------------

    query_partidos = """
        SELECT

            partido,

            SUM(valor_liquido_total) AS gasto_total,

            SUM(deputados_com_despesa)
                AS deputados_com_despesa,

            SUM(linhas) AS total_lancamentos

        FROM marts.gasto_por_partido_ano

        WHERE ano BETWEEN 2023 AND 2025

        GROUP BY partido

        ORDER BY gasto_total DESC
    """

    gastos_partido = con.execute(query_partidos).df()

    return df, gastos_partido


try:

    df, gastos_partido = carregar_dados()

except Exception as erro:

    st.error(f"Erro ao carregar os dados: {erro}")
    st.stop()


# ============================================================
# TRATAMENTO
# ============================================================

df.columns = df.columns.str.lower().str.strip()

gastos_partido.columns = (
    gastos_partido.columns.str.lower().str.strip()
)

for coluna in [
    "gasto_total",
    "participacao_pct",
    "participacao_todas_pct",
    "votos_registrados",
    "votacoes_nominais_periodo"
]:

    df[coluna] = pd.to_numeric(
        df[coluna],
        errors="coerce"
    )

for coluna in [
    "gasto_total",
    "deputados_com_despesa",
    "total_lancamentos"
]:

    gastos_partido[coluna] = pd.to_numeric(
        gastos_partido[coluna],
        errors="coerce"
    ).fillna(0)

for coluna in ["partido", "uf", "nome_parlamentar"]:

    df[coluna] = (
        df[coluna]
        .fillna("Não informado")
        .astype(str)
    )

gastos_partido["partido"] = (
    gastos_partido["partido"]
    .fillna("Não informado")
    .astype(str)
)

# Padronização dos percentuais

for coluna in [
    "participacao_pct",
    "participacao_todas_pct"
]:

    if df[coluna].max() <= 1.5:
        df[coluna] = df[coluna] * 100


# ============================================================
# FILTROS
# ============================================================

st.sidebar.header("Filtros")

partidos = sorted(df["partido"].unique())

ufs = sorted(df["uf"].unique())

partidos_selecionados = st.sidebar.multiselect(
    "Partidos",
    partidos,
    default=partidos
)

ufs_selecionadas = st.sidebar.multiselect(
    "Estados",
    ufs,
    default=ufs
)

df_filtrado = df[
    df["partido"].isin(partidos_selecionados)
    & df["uf"].isin(ufs_selecionadas)
].copy()

gastos_filtrados = gastos_partido[
    gastos_partido["partido"].isin(partidos_selecionados)
].copy()

if df_filtrado.empty:

    st.warning("Nenhum deputado encontrado.")
    st.stop()


# ============================================================
# INDICADORES
# ============================================================

st.subheader("Visão geral")

total_deputados = df_filtrado["id_deputado"].nunique()

participacao_media = (
    df_filtrado["participacao_todas_pct"].mean()
)

gasto_medio = df_filtrado["gasto_total"].mean()

gasto_total = gastos_filtrados["gasto_total"].sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Deputados analisados",
    f"{total_deputados:,}".replace(",", ".")
)

col2.metric(
    "Participação média",
    f"{participacao_media:.2f}%"
)

col3.metric(
    "Gasto médio",
    f"R$ {gasto_medio:,.2f}"
)

col4.metric(
    "Gastos totais",
    f"R$ {gasto_total:,.2f}"
)

st.divider()


# ============================================================
# GRÁFICOS: DESPESAS E PARTICIPAÇÃO NOS GASTOS
# ============================================================

col_esquerda, col_direita = st.columns(
    [1.15, 1]
)


# ============================================================
# GRÁFICO 1 - DESPESAS POR PARTIDO
# ============================================================

with col_esquerda:

    st.subheader("Despesas por partido")

    dados_barra = gastos_filtrados.sort_values(
        "gasto_total",
        ascending=True
    )

    fig_despesas = px.bar(

        dados_barra,

        x="gasto_total",

        y="partido",

        orientation="h",

        text_auto=".2s",

        labels={
            "gasto_total": "Despesas (R$)",
            "partido": "Partido"
        },

        color_discrete_sequence=[AZUL]

    )

    fig_despesas.update_traces(

        marker_line_width=0,

        textposition="outside",

        hovertemplate=(
            "<b>%{y}</b><br>"
            "Despesas: R$ %{x:,.2f}"
            "<extra></extra>"
        )

    )

    fig_despesas.update_layout(

        showlegend=False,

        height=450,

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
            r=40,
            t=30,
            b=40
        )

    )

    st.plotly_chart(
        fig_despesas,
        use_container_width=True
    )


# ============================================================
# GRÁFICO 2 - PARTICIPAÇÃO NOS GASTOS
# ============================================================

with col_direita:

    st.subheader("Participação nos gastos")

    dados_rosca = gastos_filtrados[
        gastos_filtrados["gasto_total"] > 0
    ].copy()

    fig_rosca = px.pie(

        dados_rosca,

        names="partido",

        values="gasto_total",

        hole=0.55,

        color_discrete_sequence=PALETA,

        labels={
            "partido": "Partido",
            "gasto_total": "Gastos"
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
            "Gastos: R$ %{value:,.2f}<br>"
            "Participação: %{percent}"
            "<extra></extra>"
        )

    )

    fig_rosca.update_layout(

        height=450,

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
# GRÁFICO 3 - GASTOS X PARTICIPAÇÃO
# ============================================================

st.subheader("Gastos x participação parlamentar")

df_scatter = df_filtrado.dropna(
    subset=[
        "gasto_total",
        "participacao_todas_pct"
    ]
).copy()

fig_scatter = px.scatter(

    df_scatter,

    x="gasto_total",

    y="participacao_todas_pct",

    color="partido",

    hover_name="nome_parlamentar",

    hover_data={
        "partido": True,
        "uf": True,
        "gasto_total": ":,.2f",
        "participacao_todas_pct": ":.2f"
    },

    labels={
        "gasto_total": "Gastos (R$)",
        "participacao_todas_pct": "Participação (%)",
        "partido": "Partido"
    },

    opacity=0.70

)

fig_scatter.update_layout(

    height=520,

    xaxis=dict(
        tickprefix="R$ ",
        tickformat="~s",
        title="Gastos totais"
    ),

    yaxis=dict(
        ticksuffix="%",
        title="Participação nas votações"
    ),

    legend_title="Partido"

)

st.plotly_chart(
    fig_scatter,
    use_container_width=True
)


# ============================================================
# GRÁFICO 4 - PARTICIPAÇÃO MÉDIA POR PARTIDO
# ============================================================

st.subheader("Participação média por partido")

participacao_partido = (

    df_filtrado

    .groupby("partido", as_index=False)

    .agg(

        participacao_media=(
            "participacao_todas_pct",
            "mean"
        ),

        deputados=(
            "id_deputado",
            "nunique"
        )

    )

    .sort_values(
        "participacao_media",
        ascending=True
    )

)

fig_participacao = px.bar(

    participacao_partido,

    x="participacao_media",

    y="partido",

    orientation="h",

    text="participacao_media",

    color_discrete_sequence=[AZUL],

    labels={
        "participacao_media": "Participação média (%)",
        "partido": "Partido"
    }

)

fig_participacao.update_traces(

    texttemplate="%{text:.1f}%",

    textposition="outside"

)

fig_participacao.update_layout(

    height=450,

    showlegend=False,

    xaxis=dict(
        ticksuffix="%",
        title="Participação média"
    ),

    yaxis_title=None

)

st.plotly_chart(
    fig_participacao,
    use_container_width=True
)


# ============================================================
# GRÁFICO 5 - DISTRIBUIÇÃO DA PARTICIPAÇÃO
# ============================================================

st.subheader("Distribuição da participação")

fig_distribuicao = px.histogram(

    df_filtrado,

    x="participacao_todas_pct",

    nbins=20,

    marginal="box",

    color_discrete_sequence=[AZUL],

    labels={
        "participacao_todas_pct": "Participação (%)",
        "count": "Quantidade de deputados"
    }

)

fig_distribuicao.update_layout(

    height=430,

    showlegend=False,

    xaxis_ticksuffix="%"

)

st.plotly_chart(
    fig_distribuicao,
    use_container_width=True
)


# ============================================================
# RANKING DOS DEPUTADOS
# ============================================================

st.divider()

st.subheader("Ranking parlamentar")

ranking = df_filtrado[

    [
        "nome_parlamentar",
        "partido",
        "uf",
        "gasto_total",
        "participacao_todas_pct",
        "votos_registrados",
        "total_lancamentos"
    ]

].copy()

ranking = ranking.sort_values(
    "gasto_total",
    ascending=False
)

ranking = ranking.rename(

    columns={

        "nome_parlamentar": "Deputado",

        "partido": "Partido",

        "uf": "UF",

        "gasto_total": "Gastos (R$)",

        "participacao_todas_pct": "Participação (%)",

        "votos_registrados": "Votos registrados",

        "total_lancamentos": "Lançamentos"

    }

)

st.dataframe(

    ranking.style.format({

        "Gastos (R$)": "R$ {:,.2f}",

        "Participação (%)": "{:.2f}%",

        "Votos registrados": "{:,.0f}",

        "Lançamentos": "{:,.0f}"

    }),

    use_container_width=True,

    hide_index=True,

    height=500

)


# ============================================================
# EXPORTAÇÃO
# ============================================================

csv = ranking.to_csv(

    index=False,

    sep=";",

    decimal=","

).encode("utf-8-sig")

st.download_button(

    label="📥 Exportar ranking CSV",

    data=csv,

    file_name="ranking_participacao_parlamentar.csv",

    mime="text/csv"

)


# ============================================================
# METODOLOGIA
# ============================================================

with st.expander("Sobre os dados e a metodologia"):

    st.markdown("""
    **Período:** 2023 a 2025.

    **Fonte:** dados da Câmara dos Deputados.

    **Gastos:** soma dos valores líquidos registrados
    na base de despesas por deputado e por partido.

    **Participação:** percentual de participação nas
    votações nominais, conforme a tabela
    `marts.participacao_deputado`.

    **Unidade de análise:** deputado federal.

    **Participação nos gastos:** proporção do gasto
    acumulado de cada partido em relação ao total
    dos partidos selecionados.

    Os gastos dos deputados não representam
    necessariamente os gastos administrativos
    ou eleitorais dos partidos.
    """)
