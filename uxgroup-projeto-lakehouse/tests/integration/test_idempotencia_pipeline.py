"""Reprocessar o mesmo lote não altera resultado algum (SC-002, FR-019).

Diferente de `test_carga_raw_idempotente`, que olha só RAW, este teste atravessa
as três camadas. É a prova de que a idempotência sobrevive ao merge dos fatos e
à reconstrução dos agregados — os dois lugares onde ela costuma vazar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import escalar, pipeline_completo

pytestmark = pytest.mark.requires_snowflake

# Data exclusiva deste arquivo (ver test_carga_raw_idempotente.py).
DATA = "2026-02-03"

# Campos comparados antes e depois. Cobrem contagem (duplicação) e soma (valor
# alterado) em cada camada — contar sozinho não pegaria uma linha substituída
# por outra de valor diferente.
SONDAS = {
    "raw_apostas": "select count(*) from raw_apostas",
    "stg_apostas": "select count(*) from staging.stg_apostas",
    "quarentena": "select count(*) from staging.qua_registros_rejeitados",
    "fct_linhas": "select count(*) from marts.fct_apostas",
    "fct_distintas": "select count(distinct aposta_id) from marts.fct_apostas",
    "ggr_linhas": "select count(*) from marts.agg_ggr_diario_esporte",
    "ggr_soma": "select coalesce(sum(ggr), 0) from marts.agg_ggr_diario_esporte",
    "exposicao": ("select coalesce(sum(exposicao_pendente), 0) from marts.agg_ggr_diario_esporte"),
    "volume": "select coalesce(sum(volume_apostado), 0) from marts.agg_engajamento_diario",
    "ativos": "select coalesce(sum(apostadores_ativos), 0) from marts.agg_engajamento_diario",
    "liquido": "select coalesce(sum(liquido), 0) from marts.agg_financeiro_diario",
    "rejeitados": (
        "select coalesce(sum(qtd_rejeitados_distintos), 0) from marts.agg_qualidade_lote"
    ),
}


def _fotografar(cliente) -> dict[str, object]:
    return {nome: escalar(cliente, sql) for nome, sql in SONDAS.items()}


def test_reprocessar_o_mesmo_lote_nao_muda_nada(cliente, tmp_path: Path) -> None:
    pipeline_completo(tmp_path, DATA, volume=2000)
    antes = _fotografar(cliente)

    pipeline_completo(tmp_path, DATA, volume=2000)
    depois = _fotografar(cliente)

    divergentes = {k: (antes[k], depois[k]) for k in SONDAS if antes[k] != depois[k]}
    assert not divergentes, f"reprocessamento alterou: {divergentes}"


def test_fato_nunca_duplica_aposta(cliente, tmp_path: Path) -> None:
    """`count(*)` e `count(distinct aposta_id)` têm de ser iguais.

    É o invariante que o merge de FR-019a existe para garantir; se ele quebrar,
    todo GGR passa a somar a mesma aposta duas vezes.
    """
    pipeline_completo(tmp_path, DATA, volume=2000)
    linhas = escalar(cliente, "select count(*) from marts.fct_apostas")
    distintas = escalar(cliente, "select count(distinct aposta_id) from marts.fct_apostas")
    assert linhas == distintas


def test_ggr_confere_com_calculo_independente(cliente, tmp_path: Path) -> None:
    """Recalcula o GGR direto do fato e compara com o agregado.

    O teste singular do dbt já faz isso dentro do pipeline; aqui a verificação é
    de fora, sem passar pelo mesmo SQL, o que pega um erro que estivesse no
    próprio teste.
    """
    pipeline_completo(tmp_path, DATA, volume=2000)
    do_agregado = escalar(cliente, "select coalesce(sum(ggr), 0) from marts.agg_ggr_diario_esporte")
    recalculado = escalar(
        cliente,
        """
        select coalesce(sum(valor_apostado - premio_pago), 0)
        from marts.fct_apostas
        where status in ('ganha', 'perdida')
        """,
    )
    assert float(do_agregado) == pytest.approx(float(recalculado), abs=0.01)
