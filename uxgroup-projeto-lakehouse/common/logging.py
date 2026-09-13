"""Log estruturado do pipeline.

Por que este módulo existe: a constituição exige que cada execução registre data
lógica, linhas lidas, linhas escritas, duração e resultado dos testes, e proíbe
`print` solto em código de pipeline. Uma linha JSON por evento torna o log
consultável depois — `grep` por `lote_data` reconstrói uma execução inteira — o
que `print` com texto livre não permite.

Duas decisões deliberadas:

- `ensure_ascii=False`, para que acento em nome de esporte apareça legível no
  log em vez de escapado.
- `default=str`, para que `date` e `Decimal` sejam serializáveis sem que cada
  chamador precise converter à mão; converter no lugar errado é como campo de
  data vira string em formato inconsistente.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_CONFIGURADO = False


def configurar(nivel: int = logging.INFO) -> None:
    """Instala um handler de stdout que emite uma linha por evento."""
    global _CONFIGURADO
    if _CONFIGURADO:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    raiz = logging.getLogger("bets")
    raiz.setLevel(nivel)
    raiz.handlers = [handler]
    raiz.propagate = False
    _CONFIGURADO = True


def evento(nome: str, **campos: Any) -> None:
    """Emite um evento estruturado.

    `nome` é o identificador estável do evento (por exemplo `lote_gerado`); os
    demais campos são o conteúdo. Nenhum campo é obrigatório aqui, porque a
    obrigatoriedade pertence a cada CLI e é verificada em teste.
    """
    configurar()
    payload = {"evento": nome, **campos}
    logging.getLogger("bets").info(
        json.dumps(payload, ensure_ascii=False, default=str, sort_keys=False)
    )


@contextmanager
def cronometrar(nome: str, **campos: Any) -> Iterator[dict[str, Any]]:
    """Mede a duração de um bloco e emite o evento ao sair.

    O dicionário cedido pelo `yield` pode receber campos durante a execução — é
    como as contagens de linhas entram no evento final sem precisar de variável
    global. Em caso de exceção, emite `<nome>_falhou` com a mensagem do erro
    antes de propagar: uma falha sem registro é uma execução impossível de
    diagnosticar depois.
    """
    inicio = time.monotonic()
    acumulado: dict[str, Any] = dict(campos)
    try:
        yield acumulado
    except Exception as exc:
        acumulado["duracao_s"] = round(time.monotonic() - inicio, 3)
        acumulado["erro"] = f"{type(exc).__name__}: {exc}"
        evento(f"{nome}_falhou", **acumulado)
        raise
    acumulado["duracao_s"] = round(time.monotonic() - inicio, 3)
    evento(nome, **acumulado)
