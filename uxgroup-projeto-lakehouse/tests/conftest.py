"""Fixtures compartilhadas.

Os testes de integração falam com o Snowflake de verdade — não há emulador
local para `COPY INTO`, `MERGE` e `VARIANT`, e um dublê daria falsa confiança
justamente nas partes que mais erram. Por isso eles são marcados com
`requires_snowflake` e ficam fora da suíte padrão (ver `addopts` no
`pyproject.toml`); rode-os com `pytest -m requires_snowflake` depois de
preencher o `.env`.

Sem credenciais no ambiente, os testes marcados são pulados com mensagem
explicando o que falta — nunca falham por configuração ausente, porque isso
tornaria a suíte padrão inutilizável em máquina recém-clonada.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from common.config import VARIAVEIS_SNOWFLAKE, carregar_config_snowflake

RAIZ = Path(__file__).resolve().parents[1]
DIR_DBT = RAIZ / "dbt_bets"


@pytest.fixture(scope="session")
def config_snowflake():
    ausentes = [v for v in VARIAVEIS_SNOWFLAKE if not os.environ.get(v, "").strip()]
    if ausentes:
        pytest.skip(f"credenciais do Snowflake ausentes: {', '.join(ausentes)}")
    return carregar_config_snowflake()


@pytest.fixture
def cliente(config_snowflake) -> Iterator:
    from ingestion.snowflake_client import ClienteSnowflake

    with ClienteSnowflake(config_snowflake) as c:
        yield c


@pytest.fixture(scope="session")
def dir_lotes(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("lotes")


def _rodar(comando: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    resultado = subprocess.run(
        comando, cwd=cwd or RAIZ, capture_output=True, text=True, check=False
    )
    if resultado.returncode != 0:
        raise AssertionError(
            f"comando falhou ({resultado.returncode}): {' '.join(comando)}\n"
            f"stdout:\n{resultado.stdout}\nstderr:\n{resultado.stderr}"
        )
    return resultado


def gerar_lote(destino: Path, data: str, volume: int = 2000, **taxas: float) -> None:
    """Roda a CLI do gerador como o Airflow rodaria."""
    comando = [
        sys.executable, "-m", "generator.cli",
        "--data-lote", data,
        "--volume", str(volume),
        "--saida", str(destino),
    ]
    for nome, valor in taxas.items():
        comando += [f"--{nome.replace('_', '-')}", str(valor)]
    _rodar(comando)


def carregar_raw(destino: Path, data: str) -> None:
    _rodar(
        [sys.executable, "-m", "ingestion.cli", "--data-lote", data, "--diretorio", str(destino)]
    )


def rodar_dbt(data: str, selecao: str | None = None) -> None:
    """Executa `dbt build` como a DAG executa.

    `build` intercala modelo e teste e, com `--fail-fast`, interrompe antes de
    reconstruir os modelos a jusante — é o comportamento que sustenta FR-020a
    (decisão D3).
    """
    comando = ["dbt", "build", "--fail-fast", "--vars", f"{{lote_data: '{data}'}}"]
    if selecao:
        comando += ["--select", selecao]
    _rodar(comando, cwd=DIR_DBT)


def pipeline_completo(destino: Path, data: str, volume: int = 2000, **taxas: float) -> None:
    """As três etapas na ordem da DAG."""
    gerar_lote(destino, data, volume, **taxas)
    carregar_raw(destino, data)
    rodar_dbt(data)


def contar(cliente, tabela: str, onde: str = "") -> int:
    filtro = f" WHERE {onde}" if onde else ""
    return int(cliente.executar(f"SELECT COUNT(*) FROM {tabela}{filtro}")[0][0])


def escalar(cliente, sql: str):
    return cliente.executar(sql)[0][0]
