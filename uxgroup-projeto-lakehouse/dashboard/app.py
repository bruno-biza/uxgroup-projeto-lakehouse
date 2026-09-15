"""Painel de métricas sobre as tabelas de MARTS (T087, opcional).

Por que existe: nenhum critério de sucesso depende dele (fora do escopo
obrigatório, ver spec.md § Out of Scope), mas uma consulta visual é mais
rápida de ler numa demo do que quatro `SELECT` no Snowsight. Lê só de
`BETS.MARTS`, nunca escreve nada — é um consumidor read-only do pipeline.

Rodar: `make dashboard` (ou `streamlit run dashboard/app.py` a partir da raiz
do repositório, com o `.venv` ativado e o extra `dashboard` instalado).
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import snowflake.connector  # noqa: E402
import streamlit as st  # noqa: E402

from common.config import carregar_config_snowflake  # noqa: E402

st.set_page_config(page_title="BETS · Painel de Métricas", page_icon="🎲", layout="wide")


@st.cache_resource
def conectar() -> snowflake.connector.SnowflakeConnection:
    """Uma conexão por sessão do Streamlit, reaproveitada entre reruns."""
    config = carregar_config_snowflake()
    return snowflake.connector.connect(**config.como_kwargs())


@st.cache_data(ttl=300)
def consultar(sql: str) -> pd.DataFrame:
    """Executa uma consulta e devolve DataFrame, com cache de 5 minutos.

    O cache existe porque o Streamlit reexecuta o script inteiro a cada
    interação do usuário (um clique num filtro, por exemplo) — sem isso, cada
    clique dispararia as quatro consultas de novo.
    """
    conexao = conectar()
    with conexao.cursor() as cursor:
        cursor.execute(sql)
        colunas = [coluna[0].lower() for coluna in cursor.description]
        linhas = cursor.fetchall()
    return pd.DataFrame(linhas, columns=colunas)


st.title("🎲 BETS — Painel de Métricas Diárias")
st.caption(
    "Dados 100% sintéticos, gerados por código com semente fixa — nenhum apostador "
    "ou transação aqui é real (Princípio VI da constituição do projeto)."
)

df_ggr = consultar(
    "SELECT data_aposta, esporte, total_apostado, premios_pagos, ggr, exposicao_pendente "
    "FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE ORDER BY data_aposta"
)
df_eng = consultar(
    "SELECT data_aposta, volume_apostado, ticket_medio, apostadores_ativos, qtd_apostas "
    "FROM BETS.MARTS.AGG_ENGAJAMENTO_DIARIO ORDER BY data_aposta"
)
df_fin = consultar(
    "SELECT data_transacao, total_depositado, total_sacado, liquido "
    "FROM BETS.MARTS.AGG_FINANCEIRO_DIARIO ORDER BY data_transacao"
)
df_qual = consultar(
    "SELECT lote_data, entidade, motivo, qtd_recebidos, qtd_aceitos, "
    "qtd_rejeitados_distintos, taxa_rejeicao "
    "FROM BETS.MARTS.AGG_QUALIDADE_LOTE ORDER BY lote_data"
)

if df_ggr.empty:
    st.warning(
        "BETS.MARTS.AGG_GGR_DIARIO_ESPORTE está vazia. Rode `make setup` e depois "
        "`make run-local DATA=<data>` (ou `make run DATA=<data>` com o Airflow no ar) "
        "antes de abrir o painel."
    )
    st.stop()

ultima_data = df_ggr["data_aposta"].max()
ggr_ultimo_dia = df_ggr.loc[df_ggr["data_aposta"] == ultima_data, "ggr"].sum()
exposicao_ultimo_dia = df_ggr.loc[df_ggr["data_aposta"] == ultima_data, "exposicao_pendente"].sum()
eng_ultimo_dia = df_eng.loc[df_eng["data_aposta"] == ultima_data]
qual_ultimo_lote = df_qual.loc[df_qual["lote_data"] == ultima_data]
taxa_rejeicao_media = (
    qual_ultimo_lote["taxa_rejeicao"].mean() if not qual_ultimo_lote.empty else None
)

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"GGR — {ultima_data}", f"{ggr_ultimo_dia:,.2f}")
col2.metric("Exposição pendente", f"{exposicao_ultimo_dia:,.2f}")
col3.metric(
    "Apostadores ativos",
    f"{int(eng_ultimo_dia['apostadores_ativos'].iloc[0]):,}" if not eng_ultimo_dia.empty else "—",
)
col4.metric(
    "Taxa de rejeição (média)",
    f"{taxa_rejeicao_media:.1%}" if taxa_rejeicao_media is not None else "—",
)

tab_ggr, tab_eng, tab_fin, tab_qual = st.tabs(
    ["GGR por esporte", "Engajamento", "Financeiro", "Qualidade do lote"]
)

with tab_ggr:
    esportes = sorted(df_ggr["esporte"].unique())
    selecionados = st.multiselect("Esporte", esportes, default=esportes)
    df_filtrado = df_ggr[df_ggr["esporte"].isin(selecionados)]

    st.altair_chart(
        alt.Chart(df_filtrado)
        .mark_line(point=True)
        .encode(
            x=alt.X("data_aposta:T", title="Data da aposta"),
            y=alt.Y("ggr:Q", title="GGR"),
            color=alt.Color("esporte:N", title="Esporte"),
            tooltip=["data_aposta", "esporte", "total_apostado", "premios_pagos", "ggr"],
        )
        .properties(height=340),
        width="stretch",
    )
    st.caption(
        "GGR = total apostado − prêmios pagos, só apostas resolvidas (ganha/perdida). "
        "Pode ser negativo — não há truncamento em zero."
    )

    st.altair_chart(
        alt.Chart(df_filtrado)
        .mark_bar()
        .encode(
            x=alt.X("data_aposta:T", title="Data da aposta"),
            y=alt.Y("sum(exposicao_pendente):Q", title="Exposição pendente"),
            color=alt.Color("esporte:N", title="Esporte"),
            tooltip=["data_aposta", "esporte", "exposicao_pendente"],
        )
        .properties(height=240),
        width="stretch",
    )
    st.caption(
        "Exposição pendente: valor apostado em apostas ainda em aberto. "
        "Nunca somado ao GGR — um é receita realizada, o outro é risco em aberto."
    )

with tab_eng:
    st.altair_chart(
        alt.Chart(df_eng)
        .mark_bar(color="#0B6E5B")
        .encode(
            x=alt.X("data_aposta:T", title="Data"),
            y=alt.Y("volume_apostado:Q", title="Volume apostado"),
            tooltip=["data_aposta", "volume_apostado", "apostadores_ativos", "ticket_medio"],
        )
        .properties(height=300),
        width="stretch",
    )
    st.dataframe(df_eng, width="stretch", hide_index=True)
    st.caption(
        "Inclui TODAS as apostas válidas do dia, inclusive pendente e cancelada — "
        "critério deliberadamente diferente do GGR (FR-014 vs FR-013)."
    )

with tab_fin:
    df_fin_long = df_fin.melt(
        id_vars="data_transacao",
        value_vars=["total_depositado", "total_sacado"],
        var_name="tipo",
        value_name="valor",
    )
    st.altair_chart(
        alt.Chart(df_fin_long)
        .mark_bar()
        .encode(
            x=alt.X("data_transacao:T", title="Data"),
            y=alt.Y("valor:Q", title="Valor"),
            color=alt.Color(
                "tipo:N",
                title="Tipo",
                scale=alt.Scale(
                    domain=["total_depositado", "total_sacado"], range=["#0B6E5B", "#AE3A2F"]
                ),
            ),
            tooltip=["data_transacao", "tipo", "valor"],
        )
        .properties(height=300),
        width="stretch",
    )
    st.dataframe(df_fin, width="stretch", hide_index=True)
    st.caption(
        "Líquido = depósitos − saques. Não se reconcilia com o GGR — são grandezas distintas."
    )

with tab_qual:
    df_qual_defeitos = df_qual[df_qual["motivo"] != "sem_rejeicao"]
    st.altair_chart(
        alt.Chart(df_qual_defeitos)
        .mark_bar()
        .encode(
            x=alt.X("lote_data:T", title="Lote"),
            y=alt.Y("sum(qtd_rejeitados_distintos):Q", title="Registros rejeitados"),
            color=alt.Color("motivo:N", title="Motivo"),
            tooltip=["lote_data", "entidade", "motivo", "qtd_rejeitados_distintos"],
        )
        .properties(height=320),
        width="stretch",
    )
    st.dataframe(df_qual, width="stretch", hide_index=True)
    st.caption(
        "Taxa de rejeição é informativa: nenhum valor, nem 100%, interrompe o pipeline "
        "(FR-016a). O que bloqueia é teste estrutural, não taxa."
    )
