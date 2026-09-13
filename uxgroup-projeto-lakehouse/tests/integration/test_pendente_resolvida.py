"""Aposta pendente resolvida num lote posterior (FR-019a, FR-019b).

É o requisito mais interessante do projeto e o mais fácil de implementar errado.
Três coisas têm de acontecer juntas quando o lote de amanhã traz o status final
de uma aposta de ontem:

1. a linha do fato é SUBSTITUÍDA, não acrescentada (FR-019a);
2. o GGR da data ORIGINAL da aposta muda (FR-019b);
3. a exposição pendente daquela data diminui na mesma medida.

Se só a primeira acontecer, o número está certo e o histórico está errado. Se
só a segunda, a aposta foi contada duas vezes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import carregar_raw, escalar, gerar_lote, rodar_dbt

pytestmark = pytest.mark.requires_snowflake

DIA_1 = "2026-09-10"
DIA_2 = "2026-09-11"


def _ggr_e_exposicao(cliente, data: str) -> tuple[float, float]:
    linha = cliente.executar(
        f"""
        select coalesce(sum(ggr), 0), coalesce(sum(exposicao_pendente), 0)
        from marts.agg_ggr_diario_esporte
        where data_aposta = '{data}'
        """
    )[0]
    return float(linha[0]), float(linha[1])


@pytest.fixture
def dois_lotes(cliente, tmp_path: Path) -> dict[str, tuple[float, float]]:
    """Processa o dia 1, fotografa, processa o dia 2 resolvendo pendências."""
    gerar_lote(tmp_path, DIA_1, volume=2000)
    carregar_raw(tmp_path, DIA_1)
    rodar_dbt(DIA_1)
    antes = _ggr_e_exposicao(cliente, DIA_1)

    gerar_lote(tmp_path, DIA_2, volume=2000, resolver_pendentes_de=DIA_1)
    carregar_raw(tmp_path, DIA_2)
    rodar_dbt(DIA_2)
    depois = _ggr_e_exposicao(cliente, DIA_1)

    return {"antes": antes, "depois": depois}


def test_ggr_da_data_original_e_recalculado(dois_lotes) -> None:
    ggr_antes, _ = dois_lotes["antes"]
    ggr_depois, _ = dois_lotes["depois"]
    assert ggr_antes != ggr_depois, (
        "o GGR da data original não mudou — as apostas resolvidas no lote "
        "seguinte não foram refletidas (FR-019b)"
    )


def test_exposicao_pendente_da_data_original_diminui(dois_lotes) -> None:
    _, exposicao_antes = dois_lotes["antes"]
    _, exposicao_depois = dois_lotes["depois"]
    assert exposicao_depois < exposicao_antes, (
        "a exposição pendente não caiu — as apostas continuam marcadas como "
        "pendentes depois de resolvidas"
    )


def test_aposta_resolvida_nao_duplica_no_fato(cliente, dois_lotes) -> None:
    linhas = escalar(cliente, "select count(*) from marts.fct_apostas")
    distintas = escalar(cliente, "select count(distinct aposta_id) from marts.fct_apostas")
    assert linhas == distintas, "o merge criou linha nova em vez de substituir (FR-019a)"


def test_versao_canonica_e_a_mais_recente(cliente, dois_lotes) -> None:
    """A aposta reemitida tem de estar no fato com o status FINAL, não pendente.

    Verifica a regra de FR-005 e FR-019a de fora do SQL que a implementa: as
    apostas do dia 1 que voltaram no lote do dia 2 não podem continuar
    `pendente`.
    """
    ainda_pendentes = escalar(
        cliente,
        f"""
        select count(*)
        from marts.fct_apostas
        where aposta_id like 'APS{DIA_1.replace('-', '')}%'
          and lote_data = '{DIA_2}'
          and status = 'pendente'
        """,
    )
    assert ainda_pendentes == 0
