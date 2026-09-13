"""Nenhuma data corrente implícita em código de pipeline (FR-003, Princípio IV).

Por que este teste existe como varredura de código-fonte e não como teste de
comportamento: uma chamada a `date.today()` escondida num caminho raro só
apareceria em produção, no dia em que a reexecução de um lote antigo produzisse
números diferentes. A varredura estática pega isso no primeiro commit.

`carregado_em` na camada RAW é a exceção legítima — é campo de auditoria da
carga, não insumo de nenhuma métrica — e fica no SQL, não aqui.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTES = ("generator", "ingestion")

# Chamadas proibidas como fonte de data lógica. A verificação é feita sobre a
# árvore sintática, não por expressão regular: uma busca textual casaria com a
# própria prosa que documenta a proibição, e um teste que reprova por comentário
# é um teste que alguém desliga.
PROIBIDOS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("time", "localtime"),
}

# `print` solto: a observabilidade mínima da constituição exige log estruturado.
# As CLIs são a exceção declarada no pyproject e escrevem o JSON de contrato.
EXCECOES_PRINT = {"cli.py"}


def _chamadas(modulo: Path) -> list[ast.Call]:
    arvore = ast.parse(modulo.read_text(encoding="utf-8"), filename=str(modulo))
    return [no for no in ast.walk(arvore) if isinstance(no, ast.Call)]


def _modulos() -> list[Path]:
    arquivos: list[Path] = []
    for pacote in PACOTES:
        arquivos.extend(sorted((RAIZ / pacote).rglob("*.py")))
    assert arquivos, "nenhum módulo encontrado — o teste estaria passando por vacuidade"
    return arquivos


@pytest.mark.parametrize("modulo", _modulos(), ids=lambda p: str(p.name))
def test_sem_data_corrente_implicita(modulo: Path) -> None:
    encontrados = [
        f"linha {no.lineno}: {no.func.value.id}.{no.func.attr}()"
        for no in _chamadas(modulo)
        if isinstance(no.func, ast.Attribute)
        and isinstance(no.func.value, ast.Name)
        and (no.func.value.id, no.func.attr) in PROIBIDOS
    ]
    assert not encontrados, (
        f"{modulo.relative_to(RAIZ)} usa data corrente implícita: {encontrados}. "
        "A data lógica do lote vem do orquestrador como parâmetro explícito."
    )


@pytest.mark.parametrize("modulo", _modulos(), ids=lambda p: str(p.name))
def test_sem_print_fora_das_clis(modulo: Path) -> None:
    if modulo.name in EXCECOES_PRINT:
        pytest.skip("CLI escreve em stdout por contrato")
    encontrados = [
        f"linha {no.lineno}"
        for no in _chamadas(modulo)
        if isinstance(no.func, ast.Name) and no.func.id == "print"
    ]
    assert not encontrados, f"{modulo.relative_to(RAIZ)} usa print solto: {encontrados}"


def test_cli_declara_data_lote_como_obrigatoria() -> None:
    """A data lógica não pode ter default: um default é data implícita
    disfarçada de parâmetro."""
    from generator.cli import construir_parser

    acao = next(a for a in construir_parser()._actions if a.dest == "data_lote")
    assert acao.required is True
    assert acao.default is None
