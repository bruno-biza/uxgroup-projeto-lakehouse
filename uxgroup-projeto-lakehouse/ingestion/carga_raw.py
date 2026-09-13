"""Carga do lote na camada RAW.

O fluxo por entidade é sempre o mesmo e está numa transação única:

    DELETE das linhas da data lógica  →  PUT no stage  →  COPY INTO

A ordem importa. O `DELETE` primeiro é o que garante que reprocessar uma data
substitua o lote em vez de somá-lo (decisão D1); a transação é o que impede que
uma falha no `COPY INTO` deixe a tabela sem as linhas removidas.

A lista de entidades é orientada por dados de propósito: acrescentar uma
entidade nova ao projeto é acrescentar uma entrada em `ENTIDADES`, sem tocar no
fluxo. Foi assim que `transacoes` entrou sem mudança de lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common import logging as log
from ingestion.snowflake_client import ClienteSnowflake

# nome do arquivo (sem data) -> tabela de destino
ENTIDADES: tuple[tuple[str, str], ...] = (
    ("apostadores", "raw_apostadores"),
    ("eventos", "raw_eventos"),
    ("apostas", "raw_apostas"),
    ("transacoes", "raw_transacoes"),
)


class LoteIncompletoError(FileNotFoundError):
    """Falta pelo menos um arquivo do lote.

    Distinto de lote vazio: um lote vazio legítimo tem os quatro arquivos
    presentes, cada um com apenas o cabeçalho.
    """


@dataclass
class ResultadoCarga:
    linhas_por_tabela: dict[str, int]
    linhas_removidas_antes: int

    @property
    def total_linhas(self) -> int:
        return sum(self.linhas_por_tabela.values())


def localizar_arquivos(diretorio: Path, lote_data: str) -> dict[str, Path]:
    """Resolve os quatro caminhos do lote e falha antes de qualquer conexão.

    Verificar tudo de uma vez, antes de abrir conexão, evita o pior caso: metade
    das tabelas carregada e a execução abortando por um arquivo que faltava
    desde o início.
    """
    base = diretorio / lote_data
    if not base.is_dir():
        raise LoteIncompletoError(f"diretório do lote não encontrado: {base}")

    arquivos: dict[str, Path] = {}
    faltando: list[str] = []
    for entidade, _ in ENTIDADES:
        caminho = base / f"{entidade}_{lote_data}.csv"
        if caminho.is_file():
            arquivos[entidade] = caminho
        else:
            faltando.append(caminho.name)
    if faltando:
        raise LoteIncompletoError(
            f"lote incompleto em {base}: faltam {', '.join(faltando)}"
        )
    return arquivos


def carregar(cliente: ClienteSnowflake, diretorio: Path, lote_data: str) -> ResultadoCarga:
    """Executa a carga completa do lote e devolve as contagens finais."""
    arquivos = localizar_arquivos(diretorio, lote_data)

    linhas_por_tabela: dict[str, int] = {}
    removidas_total = 0

    for entidade, tabela in ENTIDADES:
        arquivo = arquivos[entidade]
        with cliente.transacao():
            removidas = cliente.apagar_lote(tabela, lote_data)
            cliente.enviar_para_stage(arquivo, lote_data)
            linhas = cliente.copiar_para_raw(tabela, arquivo.name, lote_data)

        removidas_total += removidas
        linhas_por_tabela[tabela] = linhas
        log.evento(
            "tabela_carregada",
            lote_data=lote_data,
            tabela=tabela,
            arquivo=arquivo.name,
            linhas_removidas=removidas,
            linhas_escritas=linhas,
        )

    return ResultadoCarga(
        linhas_por_tabela=linhas_por_tabela, linhas_removidas_antes=removidas_total
    )
