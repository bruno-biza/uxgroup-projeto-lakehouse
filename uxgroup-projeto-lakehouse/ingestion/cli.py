"""CLI de carga do lote na camada RAW.

Contrato completo em `specs/002-betting-analytics-platform/contracts/cli.md`.

Nenhum segredo entra por argumento de linha de comando: credencial em `argv`
aparece em `ps` e no log de tarefa do Airflow. As sete variáveis do Snowflake
vêm do ambiente e são conferidas antes de qualquer conexão (Princípio VIII).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from common import logging as log
from common.config import ConfiguracaoAusenteError, carregar_config_snowflake
from ingestion.carga_raw import LoteIncompletoError, carregar
from ingestion.snowflake_client import ClienteSnowflake


def _data(texto: str) -> str:
    """Valida o formato e devolve a string — o SQL recebe texto ISO."""
    try:
        datetime.strptime(texto, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"data inválida: {texto!r}. Use o formato YYYY-MM-DD."
        ) from exc
    return texto


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ingestion.cli",
        description="Carrega um lote diário na camada RAW do Snowflake.",
    )
    p.add_argument("--data-lote", type=_data, required=True, help="Data lógica (YYYY-MM-DD)")
    p.add_argument("--diretorio", type=Path, required=True, help="Diretório raiz dos lotes")
    return p


def executar(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    try:
        config = carregar_config_snowflake()
    except ConfiguracaoAusenteError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    try:
        with log.cronometrar("raw_carregada", lote_data=args.data_lote) as ev:
            with ClienteSnowflake(config) as cliente:
                resultado = carregar(cliente, args.diretorio, args.data_lote)
            ev["linhas_por_tabela"] = resultado.linhas_por_tabela
            ev["linhas_escritas"] = resultado.total_linhas
            ev["linhas_removidas_antes"] = resultado.linhas_removidas_antes
    except LoteIncompletoError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(executar())
