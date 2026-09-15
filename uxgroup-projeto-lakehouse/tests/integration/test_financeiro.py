"""Movimentação financeira diária (US4, FR-015).

O caso que importa é o líquido negativo: um dia em que os saques superam os
depósitos tem de sair com sinal negativo, sem erro e sem truncamento em zero.
É o mesmo tipo de erro que truncar um GGR negativo, e aqui é mais provável
porque "líquido" soa como algo que deveria ser positivo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import escalar, pipeline_completo

pytestmark = pytest.mark.requires_snowflake

# Data exclusiva deste arquivo (ver test_carga_raw_idempotente.py).
DATA = "2026-02-02"


@pytest.fixture
def lote(cliente, tmp_path: Path):
    pipeline_completo(tmp_path, DATA, volume=4000)
    return cliente


def test_liquido_confere_com_calculo_independente(lote) -> None:
    linha = lote.executar(
        f"""
        select total_depositado, total_sacado, liquido
        from marts.agg_financeiro_diario
        where data_transacao = '{DATA}'
        """
    )
    assert linha, "nenhuma linha financeira para a data"
    for depositado, sacado, liquido in linha:
        assert float(liquido) == pytest.approx(float(depositado) - float(sacado), abs=0.01)


def test_existe_dia_com_liquido_negativo(lote) -> None:
    """O gerador usa faixa de saque maior que a de depósito exatamente para que
    este cenário ocorra e possa ser verificado."""
    negativos = escalar(lote, "select count(*) from marts.agg_financeiro_diario where liquido < 0")
    assert negativos > 0, (
        "nenhum dia com líquido negativo — o cenário de saída maior que entrada "
        "não está sendo exercitado"
    )


def test_contagens_por_tipo_somam_o_total(lote) -> None:
    divergentes = escalar(
        lote,
        """
        select count(*) from (
            select a.data_transacao
            from marts.agg_financeiro_diario a
            join (
                select data_transacao, count(*) as total
                from marts.fct_transacoes group by data_transacao
            ) f on a.data_transacao = f.data_transacao
            where a.qtd_depositos + a.qtd_saques <> f.total
        )
        """,
    )
    assert divergentes == 0


def test_transacao_nao_duplica_no_fato(lote) -> None:
    linhas = escalar(lote, "select count(*) from marts.fct_transacoes")
    distintas = escalar(lote, "select count(distinct transacao_id) from marts.fct_transacoes")
    assert linhas == distintas
