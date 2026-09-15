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

import pytest

from tests.conftest import carregar_raw, escalar, gerar_lote, rodar_dbt

pytestmark = pytest.mark.requires_snowflake

# Datas exclusivas deste arquivo (ver test_carga_raw_idempotente.py).
DIA_1 = "2026-02-04"
DIA_2 = "2026-02-05"


def _ggr_e_exposicao(cliente, data: str) -> tuple[float, float]:
    linha = cliente.executar(
        f"""
        select coalesce(sum(ggr), 0), coalesce(sum(exposicao_pendente), 0)
        from marts.agg_ggr_diario_esporte
        where data_aposta = '{data}'
        """
    )[0]
    return float(linha[0]), float(linha[1])


@pytest.fixture(scope="module")
def dois_lotes(
    config_snowflake, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, tuple[float, float]]:
    """Processa o dia 1, fotografa, processa o dia 2 resolvendo pendências.

    Escopo `module`, não o padrão `function`: as quatro funções de teste deste
    arquivo compartilham DIA_1/DIA_2 fixos contra o mesmo Snowflake real e
    persistente. Com escopo `function`, a fixture reexecutaria a cada teste —
    e a partir da segunda chamada, `gerar_lote(DIA_1)` recarregaria o conteúdo
    ORIGINAL (não resolvido) em RAW, mas a versão já resolvida na chamada
    anterior (lote_data=DIA_2, `atualizado_em` mais recente) continuaria em
    RAW e ainda venceria a deduplicação global — a foto "antes" já sairia
    pós-resolução, zerando a diferença que os testes verificam.

    Depende de `config_snowflake` (escopo `session`), não do `cliente`
    compartilhado (escopo `function`) — misturar escopo `module` com uma
    fixture `function` é erro de coleta do pytest. Abre sua própria conexão,
    fechada ao fim do módulo.

    Limpa RAW **e os fatos** de DIA_1 e DIA_2 antes de gerar qualquer coisa:
    o mesmo problema do escopo de fixture existe também ENTRE execuções da
    suíte, porque DIA_1/DIA_2 são datas fixas contra um Snowflake persistente.
    Se uma execução anterior já resolveu essas apostas, a versão resolvida
    (lote_data=DIA_2, `atualizado_em` mais recente) continua em RAW e vence a
    deduplicação global mesmo antes desta execução gerar nada — a foto
    "antes" sairia pós-resolução outra vez. Só recarregar DIA_1 não basta
    porque o competidor mora em DIA_2.

    Limpar só RAW não basta: `fct_apostas`/`fct_transacoes` são incrementais
    e guardam linhas de qualquer execução passada com `lote_data` de DIA_1 ou
    DIA_2. Apagar RAW de DIA_2 sem apagar essas linhas as deixa órfãs assim
    que `dim_eventos`/`dim_apostadores` são reconstruídas (full-refresh) sem
    o conteúdo que acabou de ser apagado — e isso derruba o `dbt build` de
    DIA_1, bem antes de DIA_2 sequer ser gerada de novo.
    """
    from ingestion.snowflake_client import ClienteSnowflake

    tmp_path = tmp_path_factory.mktemp("dois_lotes")
    with ClienteSnowflake(config_snowflake) as cliente:
        for data in (DIA_1, DIA_2):
            for tabela in (
                "raw_apostadores",
                "raw_eventos",
                "raw_apostas",
                "raw_transacoes",
            ):
                cliente.apagar_lote(tabela, data)
            cliente.executar(
                "DELETE FROM MARTS.fct_apostas WHERE lote_data = %(data)s", {"data": data}
            )
            cliente.executar(
                "DELETE FROM MARTS.fct_transacoes WHERE lote_data = %(data)s", {"data": data}
            )

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
        where aposta_id like 'APS{DIA_1.replace("-", "")}%'
          and lote_data = '{DIA_2}'
          and status = 'pendente'
        """,
    )
    assert ainda_pendentes == 0
