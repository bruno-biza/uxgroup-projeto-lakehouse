"""Escrita determinística dos arquivos CSV do lote.

Por que este módulo existe e por que é tão explícito: o Princípio VI e o
critério SC-002 cobram reprodutibilidade por checksum, não "quase igual". Três
coisas quebram isso de forma silenciosa, e as três são tratadas aqui por
desenho, não por convenção:

1. `csv.writer` usa `\\r\\n` por padrão, e em Windows o modo texto adiciona
   outro `\\r`. O checksum passaria a depender do sistema operacional. Aqui a
   escrita é manual, com `\\n` explícito e `newline=""`.
2. Iteração sobre `set` ou `dict` sem ordenação explícita varia entre
   execuções. Aqui toda coleção é ordenada pela tupla de campos já formatada,
   que é uma ordem total — inclusive entre duplicatas do mesmo identificador.
3. Formatação de float varia (`0.1 + 0.2`, notação científica em valores
   grandes). Aqui todo decimal passa por `f"{v:.2f}"`.

O formato produzido é exatamente o do contrato em
`specs/002-betting-analytics-platform/contracts/csv-batch.md`. Os dois lados
citam o mesmo documento porque divergência entre eles quebra a carga de forma
difícil de diagnosticar.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

from generator.entidades import Lote

# Ordem de colunas por arquivo. É contrato: o COPY INTO carrega por posição.
COLUNAS: dict[str, tuple[str, ...]] = {
    "apostadores": ("apostador_id", "criado_em", "estado", "atualizado_em"),
    "eventos": (
        "evento_id",
        "esporte",
        "campeonato",
        "time_casa",
        "time_visitante",
        "data_evento",
        "atualizado_em",
    ),
    "apostas": (
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
    "transacoes": (
        "transacao_id",
        "apostador_id",
        "data_transacao",
        "tipo",
        "valor",
        "atualizado_em",
    ),
}

# Colunas decimais, que recebem duas casas fixas.
_DECIMAIS = frozenset({"valor_apostado", "odd", "premio_pago", "valor"})


def formatar(coluna: str, valor: Any) -> str:
    """Converte um valor para a sua representação textual canônica.

    `None` vira campo vazio — o único jeito de representar nulo no contrato.
    Isso importa porque o file format do Snowflake usa `EMPTY_FIELD_AS_NULL`, e
    qualquer outra convenção (`NULL`, `\\N`) chegaria a RAW como a string
    literal e passaria pela validação de nulo sem ser detectada.
    """
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    if coluna in _DECIMAIS:
        return f"{float(valor):.2f}"
    return str(valor)


def _escapar(campo: str) -> str:
    """Envolve em aspas apenas quando necessário.

    Citar tudo também seria válido, mas citar só o necessário reduz a chance de
    diferença espúria entre execuções e deixa o arquivo legível a olho nu na
    hora de depurar um registro rejeitado.
    """
    if any(c in campo for c in (",", '"', "\n", "\r")):
        return '"' + campo.replace('"', '""') + '"'
    return campo


def _linhas(registros: list[Any], colunas: tuple[str, ...]) -> list[str]:
    """Serializa e ordena os registros.

    A ordenação é feita sobre as tuplas já formatadas, não sobre os objetos.
    Isso dá uma ordem total mesmo quando duas linhas compartilham o
    identificador — o caso da duplicata divergente, em que ordenar só pela
    chave natural deixaria a posição relativa indefinida.
    """
    tuplas = [
        tuple(formatar(coluna, getattr(reg, coluna)) for coluna in colunas)
        for reg in registros
    ]
    tuplas.sort()
    return [",".join(_escapar(campo) for campo in tupla) for tupla in tuplas]


def escrever_entidade(
    destino: Path, entidade: str, data_lote: date, registros: list[Any]
) -> tuple[Path, str, int]:
    """Escreve um arquivo do lote e devolve caminho, checksum e contagem.

    O checksum é calculado sobre os bytes efetivamente gravados, não sobre uma
    representação intermediária — é o mesmo valor que um `sha256sum` no arquivo
    produziria, o que permite conferir de fora do Python.
    """
    colunas = COLUNAS[entidade]
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{entidade}_{data_lote.isoformat()}.csv"

    conteudo = ",".join(colunas) + "\n"
    corpo = _linhas(registros, colunas)
    if corpo:
        conteudo += "\n".join(corpo) + "\n"

    # UTF-8 sem BOM; o BOM apareceria como lixo na primeira coluna do COPY INTO.
    bytes_ = conteudo.encode("utf-8")
    with open(caminho, "wb") as fh:
        fh.write(bytes_)

    return caminho, hashlib.sha256(bytes_).hexdigest(), len(corpo)


def escrever_lote(lote: Lote, data_lote: date, raiz: Path) -> dict[str, dict[str, Any]]:
    """Escreve os quatro arquivos do lote em `<raiz>/<data_lote>/`.

    Os quatro são sempre escritos, mesmo vazios: lote incompleto é erro de
    ingestão, enquanto lote vazio legítimo é o arquivo presente com apenas o
    cabeçalho.
    """
    destino = raiz / data_lote.isoformat()
    resultado: dict[str, dict[str, Any]] = {}
    for entidade, registros in (
        ("apostadores", lote.apostadores),
        ("eventos", lote.eventos),
        ("apostas", lote.apostas),
        ("transacoes", lote.transacoes),
    ):
        caminho, checksum, linhas = escrever_entidade(destino, entidade, data_lote, registros)
        resultado[entidade] = {
            "arquivo": caminho.name,
            "caminho": str(caminho),
            "checksum": f"sha256:{checksum}",
            "linhas": linhas,
        }
    return resultado
