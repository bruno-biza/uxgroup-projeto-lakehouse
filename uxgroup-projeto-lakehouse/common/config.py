"""Leitura de configuração de ambiente.

Por que este módulo existe: o Princípio VIII proíbe credencial no código, então
toda configuração sensível vem de variável de ambiente. O risco desse arranjo é
a falha tardia — descobrir que faltava uma variável só depois de metade do lote
carregado. Aqui a checagem é explícita e acontece antes de qualquer conexão,
nomeando a variável ausente.

Nenhuma função deste módulo tem valor default para credencial. Um default
silencioso é pior do que um erro: ele faz o programa conectar no lugar errado.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Fora do Docker (docker-compose usa `env_file: .env`), nada carrega o `.env`
# — nem o Makefile, nem pytest, nem uma CLI chamada à mão. Como todo caminho
# Python do projeto passa por este módulo antes de tocar em credencial, o
# carregamento entra aqui uma única vez, no import. `override=False` para que
# uma variável já exportada no shell continue vencendo o arquivo.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

# Variáveis exigidas pelo contrato da CLI de ingestão
# (specs/002-betting-analytics-platform/contracts/cli.md).
VARIAVEIS_SNOWFLAKE = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA_RAW",
)


class ConfiguracaoAusenteError(RuntimeError):
    """Variável de ambiente obrigatória não definida."""


@dataclass(frozen=True)
class ConfigSnowflake:
    """Credenciais e alvo da conexão, todos vindos do ambiente."""

    account: str
    user: str
    password: str
    role: str
    warehouse: str
    database: str
    schema_raw: str

    def como_kwargs(self) -> dict[str, str]:
        """Parâmetros no formato que `snowflake.connector.connect` espera."""
        return {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema_raw,
        }

    def __repr__(self) -> str:
        # A senha nunca aparece em repr: um traceback não pode vazar credencial
        # para o log do Airflow (Princípio VIII).
        return (
            f"ConfigSnowflake(account={self.account!r}, user={self.user!r}, "
            f"role={self.role!r}, warehouse={self.warehouse!r}, "
            f"database={self.database!r}, schema_raw={self.schema_raw!r}, "
            "password=<oculta>)"
        )


def exigir(nome: str) -> str:
    """Devolve a variável de ambiente ou falha nomeando o que falta."""
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise ConfiguracaoAusenteError(
            f"variável de ambiente obrigatória ausente ou vazia: {nome}. "
            "Copie .env.example para .env e preencha."
        )
    return valor


def carregar_config_snowflake() -> ConfigSnowflake:
    """Lê as sete variáveis do Snowflake, falhando na primeira que faltar.

    A checagem é feita em bloco antes de construir o objeto, para que a mensagem
    liste tudo o que falta de uma vez em vez de obrigar a descobrir uma por
    execução.
    """
    ausentes = [nome for nome in VARIAVEIS_SNOWFLAKE if not os.environ.get(nome, "").strip()]
    if ausentes:
        raise ConfiguracaoAusenteError(
            "variáveis de ambiente obrigatórias ausentes ou vazias: "
            f"{', '.join(ausentes)}. Copie .env.example para .env e preencha."
        )
    return ConfigSnowflake(
        account=exigir("SNOWFLAKE_ACCOUNT"),
        user=exigir("SNOWFLAKE_USER"),
        password=exigir("SNOWFLAKE_PASSWORD"),
        role=exigir("SNOWFLAKE_ROLE"),
        warehouse=exigir("SNOWFLAKE_WAREHOUSE"),
        database=exigir("SNOWFLAKE_DATABASE"),
        schema_raw=exigir("SNOWFLAKE_SCHEMA_RAW"),
    )
