
from pathlib import Path

import duckdb
import streamlit as st

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "camara.duckdb"
)


@st.cache_resource
def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Banco não encontrado: {DB_PATH}"
        )

    return duckdb.connect(
        str(DB_PATH),
        read_only=True
    )


@st.cache_data(ttl=300)
def run_query(query, params=None):
    con = get_connection()

    return con.execute(
        query,
        params or []
    ).df()
