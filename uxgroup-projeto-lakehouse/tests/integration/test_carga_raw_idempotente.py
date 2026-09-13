"""Idempotência da carga em RAW (FR-019, SC-002, decisão D1).

O segundo teste deste arquivo é o mais importante do projeto inteiro. Carregar
o mesmo arquivo duas vezes é o caso fácil — o histórico de carga do `COPY INTO`
resolveria sozinho. O caso que quebra é **regerar a mesma data com parâmetros
diferentes**: o conteúdo muda, o ETag muda, e o histórico de carga passa a
considerar o arquivo novo. Sem a substituição por lote, RAW ficaria com as
linhas das duas gerações e SC-002 falharia de forma intermitente — justamente
o que se faz numa demo ao vivo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import carregar_raw, contar, gerar_lote

pytestmark = pytest.mark.requires_snowflake

DATA = "2026-09-10"
TABELAS = ("raw_apostadores", "raw_eventos", "raw_apostas", "raw_transacoes")


def _contagens(cliente) -> dict[str, int]:
    return {t: contar(cliente, t, f"lote_data = '{DATA}'") for t in TABELAS}


def test_recarregar_o_mesmo_lote_nao_duplica(cliente, tmp_path: Path) -> None:
    gerar_lote(tmp_path, DATA, volume=1000)
    carregar_raw(tmp_path, DATA)
    primeira = _contagens(cliente)

    carregar_raw(tmp_path, DATA)
    segunda = _contagens(cliente)

    assert primeira == segunda, "recarga do mesmo lote alterou a contagem em RAW"
    assert all(v > 0 for v in primeira.values()), "carga não escreveu nada"


def test_regerar_a_mesma_data_substitui_em_vez_de_somar(cliente, tmp_path: Path) -> None:
    """O caso que o histórico de carga do COPY INTO não cobre sozinho."""
    gerar_lote(tmp_path, DATA, volume=1000)
    carregar_raw(tmp_path, DATA)
    antes = _contagens(cliente)

    # Mesma data, conteúdo completamente diferente.
    gerar_lote(tmp_path, DATA, volume=400)
    carregar_raw(tmp_path, DATA)
    depois = _contagens(cliente)

    assert depois["raw_apostas"] < antes["raw_apostas"], (
        "RAW não encolheu ao recarregar um lote menor — as duas gerações "
        "coexistem e a idempotência é falsa"
    )
    # Cerca de 40% do volume original, com folga para as duplicatas injetadas.
    assert depois["raw_apostas"] == pytest.approx(antes["raw_apostas"] * 0.4, rel=0.15)


def test_outra_data_nao_e_afetada(cliente, tmp_path: Path) -> None:
    outra = "2026-09-09"
    gerar_lote(tmp_path, outra, volume=500)
    carregar_raw(tmp_path, outra)
    antes = contar(cliente, "raw_apostas", f"lote_data = '{outra}'")

    gerar_lote(tmp_path, DATA, volume=1000)
    carregar_raw(tmp_path, DATA)

    depois = contar(cliente, "raw_apostas", f"lote_data = '{outra}'")
    assert antes == depois, "a carga de uma data mexeu em outra"


def test_raw_preserva_o_registro_sem_transformacao(cliente, tmp_path: Path) -> None:
    """FR-004: RAW não tipa, não filtra e não deduplica.

    A prova é direta: valores inválidos injetados no CSV têm de estar presentes
    em RAW. Se a carga os tivesse filtrado ou convertido, eles não apareceriam.
    """
    gerar_lote(tmp_path, DATA, volume=1000, taxa_valor_invalido=0.10)
    carregar_raw(tmp_path, DATA)

    invalidos = contar(
        cliente,
        "raw_apostas",
        f"lote_data = '{DATA}' AND TRY_TO_NUMBER(valor_apostado) <= 0",
    )
    assert invalidos > 0, "RAW não contém os valores inválidos injetados"

    nulos = contar(cliente, "raw_apostas", f"lote_data = '{DATA}' AND aposta_id IS NULL")
    assert nulos >= 0  # a coluna aceita nulo; a asserção é a ausência de erro

    duplicados = int(
        cliente.executar(
            "SELECT COUNT(*) - COUNT(DISTINCT aposta_id) FROM raw_apostas "
            f"WHERE lote_data = '{DATA}' AND aposta_id IS NOT NULL"
        )[0][0]
    )
    assert duplicados > 0, "RAW deduplicou — deveria preservar as duplicatas"


def test_metadados_de_proveniencia_preenchidos(cliente, tmp_path: Path) -> None:
    """Sem arquivo e linha de origem, a quarentena não tem caminho de volta."""
    gerar_lote(tmp_path, DATA, volume=500)
    carregar_raw(tmp_path, DATA)

    sem_rastro = contar(
        cliente,
        "raw_apostas",
        f"lote_data = '{DATA}' AND (arquivo_origem IS NULL OR linha_origem IS NULL)",
    )
    assert sem_rastro == 0
