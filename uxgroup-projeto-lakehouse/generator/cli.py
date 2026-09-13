"""CLI de geração do lote diário sintético.

Contrato completo em `specs/002-betting-analytics-platform/contracts/cli.md`.
Mudança em qualquer argumento ou no JSON de saída é mudança de contrato e exige
atualizar a DAG e o README no mesmo PR (Princípio X).

Nenhum argumento aceita segredo: esta CLI não fala com o Snowflake. E a data
lógica é sempre explícita — nunca `date.today()` — porque o Princípio IV exige
que reexecutar o mesmo lote produza o mesmo estado, o que é impossível se a
data vier do relógio.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from common import logging as log
from generator.config import (
    SEED_PADRAO,
    TAXA_DATA_POSTERIOR_PADRAO,
    TAXA_DUPLICADAS_PADRAO,
    TAXA_NULOS_PADRAO,
    TAXA_VALOR_INVALIDO_PADRAO,
    PerfilInvalidoError,
    PerfilLote,
)
from generator.defeitos import injetar
from generator.entidades import Lote, gerar_lote_valido
from generator.escrita import escrever_lote
from generator.pendentes import LoteAnteriorAusenteError, resolver_pendentes


def _data(texto: str) -> date:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"data inválida: {texto!r}. Use o formato YYYY-MM-DD."
        ) from exc


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m generator.cli",
        description="Gera um lote diário sintético de apostas esportivas.",
    )
    p.add_argument("--data-lote", type=_data, required=True, help="Data lógica (YYYY-MM-DD)")
    p.add_argument("--volume", type=int, required=True, help="Número de apostas do lote")
    p.add_argument("--saida", type=Path, required=True, help="Diretório raiz dos lotes")
    p.add_argument("--seed", type=int, default=SEED_PADRAO, help="Semente (padrão: 42)")
    p.add_argument("--taxa-duplicadas", type=float, default=TAXA_DUPLICADAS_PADRAO)
    p.add_argument("--taxa-nulos", type=float, default=TAXA_NULOS_PADRAO)
    p.add_argument("--taxa-valor-invalido", type=float, default=TAXA_VALOR_INVALIDO_PADRAO)
    p.add_argument("--taxa-data-posterior", type=float, default=TAXA_DATA_POSTERIOR_PADRAO)
    p.add_argument(
        "--resolver-pendentes-de",
        type=_data,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Reemite apostas que ficaram pendentes no lote desta data, com "
            "status final e marcador de atualização posterior. É o que produz "
            "o cenário de FR-019b: o GGR da data original é recalculado."
        ),
    )
    return p


def executar(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    try:
        perfil = PerfilLote(
            data_lote=args.data_lote,
            volume_apostas=args.volume,
            seed=args.seed,
            taxa_duplicadas=args.taxa_duplicadas,
            taxa_nulos=args.taxa_nulos,
            taxa_valor_invalido=args.taxa_valor_invalido,
            taxa_data_posterior=args.taxa_data_posterior,
        )
    except PerfilInvalidoError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    try:
        with log.cronometrar(
            "lote_gerado", lote_data=perfil.data_lote, seed=perfil.seed
        ) as ev:
            lote = gerar_lote_valido(perfil)
            lote, defeitos = injetar(lote, perfil)

            # As pendências reemitidas entram DEPOIS da injeção de defeitos: são
            # correções de um lote anterior, não registros novos sujeitos a
            # sujeira nova.
            reemitidas = 0
            if args.resolver_pendentes_de is not None:
                resolvidas = resolver_pendentes(
                    raiz=args.saida,
                    data_anterior=args.resolver_pendentes_de,
                    data_lote=perfil.data_lote,
                    seed=perfil.seed,
                )
                lote = Lote(
                    apostadores=lote.apostadores,
                    eventos=lote.eventos,
                    apostas=lote.apostas + resolvidas,
                    transacoes=lote.transacoes,
                )
                reemitidas = len(resolvidas)

            arquivos = escrever_lote(lote, perfil.data_lote, args.saida)

            ev["pendentes_resolvidas"] = reemitidas
            ev["linhas"] = {ent: dados["linhas"] for ent, dados in arquivos.items()}
            ev["linhas_escritas"] = sum(dados["linhas"] for dados in arquivos.values())
            ev["defeitos"] = defeitos
            ev["checksums"] = {
                dados["arquivo"]: dados["checksum"] for dados in arquivos.values()
            }
            ev["destino"] = str(args.saida / perfil.data_lote.isoformat())
    except LoteAnteriorAusenteError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(executar())
