"""Rastreabilidade da quarentena e comportamento da taxa de rejeição.

Cobre `SC-003`, `SC-004`, `SC-005` e `SC-009` — os quatro critérios que
sustentam a US2. O último é o contra-exemplo importante: taxa alta de rejeição
NÃO bloqueia (`FR-016a`). Só teste estrutural bloqueia.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import escalar, pipeline_completo

pytestmark = pytest.mark.requires_snowflake

DATA = "2026-09-10"


@pytest.fixture
def lote_sujo(cliente, tmp_path: Path):
    """Lote com proporções conhecidas de cada defeito."""
    pipeline_completo(
        tmp_path,
        DATA,
        volume=2000,
        taxa_duplicadas=0.05,
        taxa_nulos=0.03,
        taxa_valor_invalido=0.02,
        taxa_data_posterior=0.02,
    )
    return cliente


def test_nenhum_registro_invalido_nas_metricas(lote_sujo) -> None:
    """SC-003: a contagem de inválidos nos fatos é zero."""
    invalidos = escalar(
        lote_sujo,
        """
        select count(*) from marts.fct_apostas
        where valor_apostado <= 0
           or aposta_id is null
           or status not in ('ganha', 'perdida', 'pendente', 'cancelada')
           or (status in ('perdida', 'pendente', 'cancelada') and premio_pago <> 0)
        """,
    )
    assert invalidos == 0


def test_registro_rejeitado_mantem_rastro_completo(lote_sujo) -> None:
    """SC-004: conteúdo original, arquivo e linha de origem, motivos."""
    sem_rastro = escalar(
        lote_sujo,
        f"""
        select count(*) from staging.qua_registros_rejeitados
        where lote_data = '{DATA}'
          and (registro_original is null
               or arquivo_origem is null
               or linha_origem is null
               or array_size(motivos) = 0)
        """,
    )
    assert sem_rastro == 0

    total = escalar(
        lote_sujo,
        f"select count(*) from staging.qua_registros_rejeitados where lote_data = '{DATA}'",
    )
    assert total > 0, "nenhum registro em quarentena — os defeitos não foram detectados"


def test_invariante_recebidos_aceitos_rejeitados(lote_sujo) -> None:
    """SC-005: recebidos = aceitos + rejeitados distintos, por lote e entidade."""
    divergentes = escalar(
        lote_sujo,
        f"""
        select count(*) from (
            select lote_data, entidade,
                   max(qtd_recebidos) as r,
                   max(qtd_aceitos) as a,
                   max(qtd_rejeitados_distintos) as d
            from marts.agg_qualidade_lote
            where lote_data = '{DATA}'
            group by lote_data, entidade
            having max(qtd_recebidos) <> max(qtd_aceitos) + max(qtd_rejeitados_distintos)
        )
        """,
    )
    assert divergentes == 0


def test_os_quatro_motivos_injetados_aparecem(lote_sujo) -> None:
    """Ponte entre o que o gerador injetou e o que o pipeline detectou."""
    motivos = {
        linha[0]
        for linha in lote_sujo.executar(
            f"""
            select distinct motivo from marts.agg_qualidade_lote
            where lote_data = '{DATA}' and entidade = 'apostas'
            """
        )
    }
    esperados = {
        "duplicata",
        "nulo_obrigatorio",
        "valor_nao_positivo",
        "data_posterior_ao_evento",
    }
    assert esperados <= motivos, f"motivos ausentes: {esperados - motivos}"


def test_registro_com_varios_motivos_conta_uma_vez(lote_sujo) -> None:
    """Caso de borda do cenário 4 da US2.

    A soma por motivo é maior ou igual à contagem distinta; quando é
    estritamente maior, existe registro com múltiplos motivos — e é justamente
    nesse caso que confundir as duas colunas produziria um total inflado.
    """
    linha = lote_sujo.executar(
        f"""
        select sum(qtd_rejeitados), max(qtd_rejeitados_distintos)
        from marts.agg_qualidade_lote
        where lote_data = '{DATA}' and entidade = 'apostas'
        """
    )[0]
    soma_por_motivo, distintos = int(linha[0]), int(linha[1])
    assert soma_por_motivo >= distintos


def test_taxa_alta_de_rejeicao_nao_bloqueia(cliente, tmp_path: Path) -> None:
    """SC-009 e FR-016a: 60% de rejeição e o pipeline conclui com sucesso.

    Se `pipeline_completo` levantar, a asserção nem é alcançada — o próprio
    sucesso da chamada é metade do teste.
    """
    outra = "2026-09-12"
    pipeline_completo(
        tmp_path,
        outra,
        volume=2000,
        taxa_duplicadas=0.0,
        taxa_nulos=0.0,
        taxa_valor_invalido=0.60,
        taxa_data_posterior=0.0,
    )

    taxa = escalar(
        cliente,
        f"""
        select max(taxa_rejeicao) from marts.agg_qualidade_lote
        where lote_data = '{outra}' and entidade = 'apostas'
        """,
    )
    assert float(taxa) > 0.5, "a taxa alta não foi registrada no resumo de qualidade"

    # E as métricas foram calculadas sobre o que sobrou.
    apostas_no_fato = escalar(
        cliente,
        f"select count(*) from marts.fct_apostas where lote_data = '{outra}'",
    )
    assert apostas_no_fato > 0, "nada chegou ao fato — o pipeline descartou o lote inteiro"


def test_lote_limpo_aparece_no_resumo(cliente, tmp_path: Path) -> None:
    """Entidade sem rejeição tem de ser visível, com motivo `sem_rejeicao`.

    Ausência de linha seria indistinguível de lote não processado.
    """
    limpa = "2026-09-13"
    pipeline_completo(
        tmp_path,
        limpa,
        volume=1000,
        taxa_duplicadas=0.0,
        taxa_nulos=0.0,
        taxa_valor_invalido=0.0,
        taxa_data_posterior=0.0,
    )
    linhas = escalar(
        cliente,
        f"""
        select count(*) from marts.agg_qualidade_lote
        where lote_data = '{limpa}' and motivo = 'sem_rejeicao'
        """,
    )
    assert linhas > 0
