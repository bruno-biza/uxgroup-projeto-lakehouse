"""Aplica os scripts SQL de bootstrap do Snowflake, em ordem.

Por que existe em vez de um `snowsql setup.sql`: o SnowSQL é uma instalação
extra que o avaliador teria de fazer antes de rodar qualquer coisa, e o
`snowflake-connector-python` já é dependência do projeto. Menos pré-requisito no
README é menos chance de `SC-008` falhar.

Todos os scripts usam `IF NOT EXISTS`, então aplicar duas vezes não é erro —
`make setup` é idempotente como o quickstart promete.
"""

from __future__ import annotations

import sys
from pathlib import Path

import snowflake.connector

from common import logging as log
from common.config import ConfiguracaoAusenteError, carregar_config_snowflake

DIRETORIO = Path(__file__).resolve().parent
ORDEM = (
    "01_warehouse.sql",
    "02_database.sql",
    "03_stage.sql",
    "04_raw_tables.sql",
)


def separar_comandos(sql: str) -> list[str]:
    """Divide o script em comandos.

    Divisão simples por `;` porque os scripts de bootstrap são DDL direto, sem
    corpo de procedure nem literal contendo ponto e vírgula. Se isso mudar, o
    lugar de resolver é aqui, não no chamador.
    """
    return [c.strip() for c in sql.split(";") if c.strip()]


def aplicar() -> int:
    try:
        config = carregar_config_snowflake()
    except ConfiguracaoAusenteError as exc:
        print(f"erro: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    # A conexão do bootstrap não pode exigir o database nem o warehouse: eles
    # ainda não existem na primeira execução.
    parametros = config.como_kwargs()
    parametros.pop("database", None)
    parametros.pop("schema", None)
    parametros.pop("warehouse", None)

    with log.cronometrar("bootstrap_aplicado") as ev:
        aplicados: list[str] = []
        conexao = snowflake.connector.connect(**parametros)
        try:
            with conexao.cursor() as cur:
                for nome in ORDEM:
                    script = (DIRETORIO / nome).read_text(encoding="utf-8")
                    for comando in separar_comandos(script):
                        cur.execute(comando)
                    aplicados.append(nome)
                    log.evento("script_aplicado", script=nome)
                # A partir daqui o contexto existe; deixa a sessão apontada para
                # ele para que um erro de contexto apareça já no bootstrap.
                cur.execute(f"USE WAREHOUSE {config.warehouse}")
                cur.execute(f"USE DATABASE {config.database}")
        finally:
            conexao.close()
        ev["scripts"] = aplicados

    return 0


if __name__ == "__main__":
    raise SystemExit(aplicar())
