"""Contagem efetiva dos defeitos injetados (US2, contrato da CLI).

Estas contagens são a referência contra a qual `agg_qualidade_lote` é conferido
no cenário 4 do quickstart. Se a injeção não respeitar a taxa pedida, não há
como saber se uma divergência no resumo de qualidade é erro do pipeline ou do
gerador — e o teste mais importante da US2 perde o referencial.
"""

from __future__ import annotations

from datetime import date

import pytest

from generator.config import PerfilLote
from generator.defeitos import injetar
from generator.entidades import gerar_lote_valido

DATA = date(2026, 9, 10)
VOLUME = 2000


def _lote_sujo(**taxas: float) -> tuple[list, dict[str, int], int]:
    perfil = PerfilLote(data_lote=DATA, volume_apostas=VOLUME, **taxas)
    limpo = gerar_lote_valido(perfil)
    sujo, contagens = injetar(limpo, perfil)
    return sujo.apostas, contagens, len(limpo.apostas)


@pytest.mark.parametrize(
    ("parametro", "motivo", "taxa"),
    [
        ("taxa_duplicadas", "duplicata", 0.05),
        ("taxa_nulos", "nulo_obrigatorio", 0.03),
        ("taxa_valor_invalido", "valor_nao_positivo", 0.02),
        ("taxa_data_posterior", "data_posterior_ao_evento", 0.02),
    ],
)
def test_contagem_respeita_a_taxa(parametro: str, motivo: str, taxa: float) -> None:
    """Tolerância de uma linha, como o contrato da CLI promete."""
    zeradas = {
        "taxa_duplicadas": 0.0,
        "taxa_nulos": 0.0,
        "taxa_valor_invalido": 0.0,
        "taxa_data_posterior": 0.0,
    }
    zeradas[parametro] = taxa
    _, contagens, total = _lote_sujo(**zeradas)
    esperado = int(total * taxa)
    assert abs(contagens[motivo] - esperado) <= 1


def test_duplicatas_sao_linhas_adicionais_com_mesmo_id() -> None:
    """A duplicata acrescenta linha; não substitui a original.

    É o que faz `raw_apostas` receber mais linhas que `--volume` e o que dá à
    regra "vence o mais recente" algo para decidir.
    """
    apostas, contagens, total = _lote_sujo(
        taxa_duplicadas=0.05, taxa_nulos=0.0, taxa_valor_invalido=0.0, taxa_data_posterior=0.0
    )
    assert len(apostas) == total + contagens["duplicata"]
    ids = [a.aposta_id for a in apostas]
    assert len(ids) - len(set(ids)) == contagens["duplicata"]


def test_duplicata_tem_atualizado_em_mais_recente() -> None:
    """Sem isso, a regra de desempate de FR-005 não teria como escolher."""
    apostas, _, _ = _lote_sujo(
        taxa_duplicadas=0.05, taxa_nulos=0.0, taxa_valor_invalido=0.0, taxa_data_posterior=0.0
    )
    por_id: dict[str, list] = {}
    for aposta in apostas:
        por_id.setdefault(aposta.aposta_id, []).append(aposta)
    repetidos = {k: v for k, v in por_id.items() if len(v) > 1}
    assert repetidos, "nenhuma duplicata gerada"
    for versoes in repetidos.values():
        instantes = [v.atualizado_em for v in versoes]
        assert len(set(instantes)) == len(instantes), "empate no marcador de atualização"


def test_valor_invalido_gera_zero_e_negativo() -> None:
    """A spec pede que zero e negativo sejam contabilizados em separado, então
    os dois têm de existir no lote."""
    apostas, _, _ = _lote_sujo(
        taxa_duplicadas=0.0, taxa_nulos=0.0, taxa_valor_invalido=0.10, taxa_data_posterior=0.0
    )
    valores = [a.valor_apostado for a in apostas if a.valor_apostado is not None]
    assert any(v == 0.0 for v in valores)
    assert any(v < 0.0 for v in valores)


def test_data_posterior_e_realmente_posterior() -> None:
    perfil = PerfilLote(
        data_lote=DATA,
        volume_apostas=VOLUME,
        taxa_duplicadas=0.0,
        taxa_nulos=0.0,
        taxa_valor_invalido=0.0,
        taxa_data_posterior=0.10,
    )
    limpo = gerar_lote_valido(perfil)
    sujo, contagens = injetar(limpo, perfil)
    data_evento = {e.evento_id: e.data_evento for e in sujo.eventos}
    posteriores = [
        a
        for a in sujo.apostas
        if a.data_aposta is not None
        and a.evento_id in data_evento
        and a.data_aposta > data_evento[a.evento_id]
    ]
    assert len(posteriores) >= contagens["data_posterior_ao_evento"] - 1


def test_lote_sem_taxas_nao_tem_defeito() -> None:
    """O núcleo válido tem de ser gerável sozinho — é a base de comparação das
    métricas antes de introduzir sujeira."""
    apostas, contagens, total = _lote_sujo(
        taxa_duplicadas=0.0, taxa_nulos=0.0, taxa_valor_invalido=0.0, taxa_data_posterior=0.0
    )
    assert contagens == {
        "duplicata": 0,
        "nulo_obrigatorio": 0,
        "valor_nao_positivo": 0,
        "data_posterior_ao_evento": 0,
    }
    assert len(apostas) == total
    assert all(a.valor_apostado > 0 for a in apostas)
    assert all(a.premio_pago == 0.0 for a in apostas if a.status != "ganha")


def test_injecao_nao_altera_o_nucleo_valido() -> None:
    """Semente derivada: gerar com e sem injeção produz o mesmo núcleo.

    Essa propriedade é o que permite isolar o efeito da sujeira ao depurar um
    número que não fecha.
    """
    perfil = PerfilLote(data_lote=DATA, volume_apostas=500)
    a = gerar_lote_valido(perfil)
    b = gerar_lote_valido(perfil)
    assert [x.aposta_id for x in a.apostas] == [x.aposta_id for x in b.apostas]
    assert [x.valor_apostado for x in a.apostas] == [x.valor_apostado for x in b.apostas]
