"""Acesso ao Snowflake para a carga da camada RAW.

Este é o único ponto do projeto que fala com o warehouse pela via Python (o dbt
tem o seu próprio). Concentrar aqui tem um motivo prático: `PUT` e `COPY INTO`
são as duas operações em que um detalhe errado custa caro — `PUT` sem
`OVERWRITE` deixa arquivo velho no stage, `COPY INTO` sem `FORCE` ignora
silenciosamente um arquivo já visto — e é mais fácil revisar uma vez do que em
cada chamador.

Sobre `ON_ERROR = ABORT_STATEMENT`: parece frágil num projeto cujo dado é sujo
de propósito, mas é justamente o contrário. Como todas as colunas de RAW são
`VARCHAR` (ver `snowflake_setup/04_raw_tables.sql`), não existe conversão que
possa falhar. Um erro aqui significa arquivo corrompido — problema de
infraestrutura — e não dado inválido, que é problema esperado e tratado pela
quarentena em STAGING. Abortar na primeira é o comportamento correto.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import snowflake.connector

from common.config import ConfigSnowflake

# Colunas de negócio por tabela, na ordem exata do CSV. O COPY INTO carrega por
# posição, então esta ordem é contrato compartilhado com
# `specs/002-betting-analytics-platform/contracts/csv-batch.md`.
COLUNAS_NEGOCIO: dict[str, tuple[str, ...]] = {
    "raw_apostadores": ("apostador_id", "criado_em", "estado", "atualizado_em"),
    "raw_eventos": (
        "evento_id",
        "esporte",
        "campeonato",
        "time_casa",
        "time_visitante",
        "data_evento",
        "atualizado_em",
    ),
    "raw_apostas": (
        "aposta_id",
        "apostador_id",
        "evento_id",
        "data_aposta",
        "valor_apostado",
        "odd",
        "status",
        "premio_pago",
        "atualizado_em",
    ),
    "raw_transacoes": (
        "transacao_id",
        "apostador_id",
        "data_transacao",
        "tipo",
        "valor",
        "atualizado_em",
    ),
}

STAGE = "STG_LOTES"
FILE_FORMAT = "FF_CSV_BETS"


class ClienteSnowflake:
    """Envoltório fino sobre a conexão, com as operações da carga."""

    def __init__(self, config: ConfigSnowflake) -> None:
        self._config = config
        self._conn: Any = None

    def __enter__(self) -> ClienteSnowflake:
        self._conn = snowflake.connector.connect(**self._config.como_kwargs())
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conexao(self) -> Any:
        if self._conn is None:
            raise RuntimeError("cliente usado fora do gerenciador de contexto")
        return self._conn

    def executar(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        with self.conexao.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()

    @contextmanager
    def transacao(self) -> Iterator[None]:
        """Transação explícita.

        A carga de cada tabela é atômica: o `DELETE` do lote e o `COPY INTO` que
        o repõe acontecem juntos. Sem isso, uma falha no meio deixaria a tabela
        sem as linhas que o `DELETE` removeu — pior que o estado anterior.
        """
        self.executar("BEGIN")
        try:
            yield
        except Exception:
            self.executar("ROLLBACK")
            raise
        self.executar("COMMIT")

    # --- operações da carga ------------------------------------------------

    def contar_lote(self, tabela: str, lote_data: str) -> int:
        sql = f"SELECT COUNT(*) FROM {tabela} WHERE lote_data = %(lote_data)s"
        return int(self.executar(sql, {"lote_data": lote_data})[0][0])

    def apagar_lote(self, tabela: str, lote_data: str) -> int:
        """Remove as linhas da data lógica antes da recarga (decisão D1).

        É o que torna a idempotência independente do histórico de carga do
        `COPY INTO`, que só reconhece o par nome do arquivo + ETag e portanto
        recarregaria um lote regerado com outros parâmetros.
        """
        removidas = self.contar_lote(tabela, lote_data)
        self.executar(
            f"DELETE FROM {tabela} WHERE lote_data = %(lote_data)s",
            {"lote_data": lote_data},
        )
        return removidas

    def enviar_para_stage(self, arquivo: Path, lote_data: str) -> None:
        """`PUT` do arquivo no stage interno.

        `OVERWRITE = TRUE` é necessário porque o nome do arquivo é determinístico:
        sem ele, um lote regerado seria enviado como `arquivo.csv.gz.1` e o
        `COPY INTO` carregaria as duas versões.

        `AUTO_COMPRESS = FALSE` mantém o arquivo legível no stage, o que ajuda a
        depurar um registro rejeitado, e o ganho de compressão é irrelevante
        neste volume.
        """
        caminho = arquivo.resolve().as_posix()
        self.executar(
            f"PUT 'file://{caminho}' '@{STAGE}/{lote_data}/' OVERWRITE = TRUE AUTO_COMPRESS = FALSE"
        )
        self._aguardar_visibilidade_no_stage(arquivo.name, lote_data)

    def _aguardar_visibilidade_no_stage(
        self, arquivo: str, lote_data: str, tentativas: int = 5, espera_s: float = 0.5
    ) -> None:
        """Confirma no `LIST` que o arquivo já está visível antes do `COPY INTO`.

        Mitiga uma janela de propagação rara entre `PUT` e `COPY INTO`
        observada em produção: disparar o `COPY INTO` imediato demais depois
        do `PUT` pode não encontrar o arquivo ainda, e um padrão de stage sem
        correspondência não é erro para o `COPY INTO` — ele completa com
        sucesso tendo carregado zero linhas, silenciosamente. Falhar alto e
        claro aqui é melhor do que uma tabela RAW incompleta sem aviso.
        """
        caminho_stage = f"@{STAGE}/{lote_data}/{arquivo}"
        for _ in range(tentativas):
            if self.executar(f"LIST '{caminho_stage}'"):
                return
            time.sleep(espera_s)
        raise RuntimeError(
            f"arquivo {arquivo} não apareceu em {caminho_stage} após "
            f"{tentativas} tentativas — carga abortada antes do COPY INTO"
        )

    def copiar_para_raw(self, tabela: str, arquivo: str, lote_data: str) -> int:
        """`COPY INTO` com os metadados de proveniência.

        `METADATA$FILENAME` e `METADATA$FILE_ROW_NUMBER` são o que permite ao
        engenheiro de dados voltar de um registro em quarentena até a linha
        exata do CSV (FR-010, SC-004).

        `FORCE = TRUE` desliga o histórico de carga: quem garante a idempotência
        é o `DELETE` da mesma transação, não o histórico.
        """
        colunas = COLUNAS_NEGOCIO[tabela]
        selecao = ", ".join(f"t.${i}" for i in range(1, len(colunas) + 1))
        lista_colunas = ", ".join(colunas)
        sql = f"""
            COPY INTO {tabela} ({lista_colunas}, arquivo_origem, linha_origem,
                                 carregado_em, lote_data)
            FROM (
                SELECT {selecao},
                       METADATA$FILENAME,
                       METADATA$FILE_ROW_NUMBER,
                       CURRENT_TIMESTAMP(),
                       TO_DATE('{lote_data}')
                FROM '@{STAGE}/{lote_data}/{arquivo}' (FILE_FORMAT => {FILE_FORMAT}) t
            )
            FILE_FORMAT = (FORMAT_NAME = {FILE_FORMAT})
            FORCE = TRUE
            ON_ERROR = ABORT_STATEMENT
        """
        self.executar(sql)
        return self.contar_lote(tabela, lote_data)
