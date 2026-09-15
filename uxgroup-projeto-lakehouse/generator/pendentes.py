"""Resolução de apostas pendentes de um lote anterior.

Por que este módulo existe: `FR-019a` e `FR-019b` exigem que um lote posterior
possa trazer a mesma aposta com status final, e que as métricas da data
original sejam recalculadas. Sem um mecanismo que produza esse dado, o requisito
mais interessante do projeto não teria como ser demonstrado nem testado — e um
requisito que não se pode exercitar é um requisito que não se sabe se funciona.

O que ele faz: lê o arquivo de apostas de um lote já gerado, escolhe uma fração
determinística das que ficaram `pendente` e as reemite com status final,
`premio_pago` coerente e `atualizado_em` posterior. Essas linhas entram no lote
corrente, com o `aposta_id` e a `data_aposta` ORIGINAIS — é essa combinação que
faz o merge do fato substituir a linha antiga e o agregado da data antiga ser
recalculado.
"""

from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from generator.config import FRACAO_PENDENTES_RESOLVIDAS
from generator.entidades import Aposta


class LoteAnteriorAusenteError(FileNotFoundError):
    """O lote anterior indicado não existe no diretório de saída."""


def caminho_apostas(raiz: Path, data: date) -> Path:
    return raiz / data.isoformat() / f"apostas_{data.isoformat()}.csv"


def _ler_pendentes(caminho: Path) -> list[dict[str, str]]:
    """Lê as apostas pendentes do CSV do lote anterior.

    Linhas com QUALQUER campo obrigatório vazio são ignoradas: são os defeitos
    injetados naquele lote, que já foram para a quarentena e não têm status a
    resolver. A checagem cobre todos os campos usados adiante — a primeira
    versão deste filtro só olhava três deles e quebrava na primeira aposta com
    `data_aposta` anulada pela injeção de nulos.
    """
    obrigatorios = (
        "aposta_id",
        "apostador_id",
        "evento_id",
        "data_aposta",
        "valor_apostado",
        "odd",
    )
    with open(caminho, encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    return [
        linha
        for linha in linhas
        if linha.get("status") == "pendente" and all(linha.get(campo) for campo in obrigatorios)
    ]


def resolver_pendentes(
    raiz: Path,
    data_anterior: date,
    data_lote: date,
    seed: int,
    fracao: float = FRACAO_PENDENTES_RESOLVIDAS,
) -> list[Aposta]:
    """Devolve as apostas do lote anterior reemitidas com status final.

    A seleção é ordenada e semeada, então a mesma entrada produz sempre a mesma
    saída — o Princípio VI vale também para esta etapa.
    """
    caminho = caminho_apostas(raiz, data_anterior)
    if not caminho.is_file():
        raise LoteAnteriorAusenteError(
            f"lote anterior não encontrado: {caminho}. "
            "Gere o lote de origem antes de resolver as pendências dele."
        )

    pendentes = _ler_pendentes(caminho)
    # Ordena pela chave natural antes de sortear: a ordem de leitura do CSV já é
    # determinística, mas depender dela tornaria este módulo frágil a qualquer
    # mudança na escrita.
    pendentes.sort(key=lambda linha: linha["aposta_id"])

    rng = random.Random(f"{seed}:{data_anterior.isoformat()}:{data_lote.isoformat()}")
    quantidade = int(len(pendentes) * fracao)
    escolhidas = pendentes[:quantidade]

    resolvidas: list[Aposta] = []
    for linha in escolhidas:
        valor = float(linha["valor_apostado"])
        odd = float(linha["odd"])
        ganhou = rng.random() < 0.35
        status = "ganha" if ganhou else "perdida"
        resolvidas.append(
            Aposta(
                aposta_id=linha["aposta_id"],
                apostador_id=linha["apostador_id"],
                evento_id=linha["evento_id"],
                # Data ORIGINAL da aposta. É o que faz o agregado daquela data
                # ser recalculado (FR-019b) em vez de a aposta migrar de dia.
                data_aposta=datetime.strptime(linha["data_aposta"], "%Y-%m-%d").date(),
                valor_apostado=valor,
                odd=odd,
                status=status,
                premio_pago=round(valor * odd, 2) if ganhou else 0.0,
                # Marcador posterior ao original: é o que faz esta versão vencer
                # a disputa de FR-005 e FR-019a.
                atualizado_em=datetime.combine(data_lote, datetime.min.time())
                + timedelta(seconds=rng.randrange(0, 86_400)),
            )
        )
    return resolvidas
