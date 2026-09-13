"""Reemissão determinística de apostas pendentes (FR-019a).

Estes testes rodam sem Snowflake: verificam que o gerador produz o dado de
entrada correto para o cenário de FR-019b. Sem isso, o teste de integração
correspondente falharia por falta de insumo e não por defeito no pipeline —
distinção que custa tempo de depuração.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from generator.config import PerfilLote
from generator.defeitos import injetar
from generator.entidades import gerar_lote_valido
from generator.escrita import escrever_lote
from generator.pendentes import LoteAnteriorAusenteError, resolver_pendentes

DIA_1 = date(2026, 9, 10)
DIA_2 = date(2026, 9, 11)


@pytest.fixture
def lote_dia_1(tmp_path: Path) -> Path:
    perfil = PerfilLote(data_lote=DIA_1, volume_apostas=1000)
    lote, _ = injetar(gerar_lote_valido(perfil), perfil)
    escrever_lote(lote, DIA_1, tmp_path)
    return tmp_path


def test_reemite_apostas_do_lote_anterior(lote_dia_1: Path) -> None:
    resolvidas = resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42)
    assert resolvidas, "nenhuma pendência resolvida"
    assert all(a.aposta_id.startswith("APS20260910") for a in resolvidas)


def test_status_final_e_premio_coerente(lote_dia_1: Path) -> None:
    for aposta in resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42):
        assert aposta.status in ("ganha", "perdida")
        if aposta.status == "perdida":
            assert aposta.premio_pago == 0.0
        else:
            assert aposta.premio_pago == pytest.approx(
                round(aposta.valor_apostado * aposta.odd, 2)
            )


def test_data_da_aposta_permanece_a_original(lote_dia_1: Path) -> None:
    """É o que faz o agregado da data ANTIGA ser recalculado (FR-019b).

    Se a data migrasse para o lote corrente, a aposta simplesmente mudaria de
    dia e o histórico continuaria errado.

    A comparação é contra a data que está no CSV de origem, não contra a data do
    lote: parte das apostas do lote anterior carrega o defeito
    `data_posterior_ao_evento` de propósito, e a data delas é maior que a data
    do lote por construção. Elas serão rejeitadas em STAGING de novo, o que é o
    comportamento correto — reemiti-las não as torna válidas.
    """
    caminho = lote_dia_1 / DIA_1.isoformat() / f"apostas_{DIA_1.isoformat()}.csv"
    with open(caminho, encoding="utf-8", newline="") as fh:
        origem = {
            linha["aposta_id"]: linha["data_aposta"] for linha in csv.DictReader(fh)
        }
    for aposta in resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42):
        assert aposta.data_aposta.isoformat() == origem[aposta.aposta_id]


def test_marcador_de_atualizacao_e_posterior(lote_dia_1: Path) -> None:
    """Sem marcador mais recente, a versão resolvida perderia a disputa de
    FR-005 para a versão pendente original."""
    caminho = lote_dia_1 / DIA_1.isoformat() / f"apostas_{DIA_1.isoformat()}.csv"
    with open(caminho, encoding="utf-8", newline="") as fh:
        original = {
            linha["aposta_id"]: linha["atualizado_em"] for linha in csv.DictReader(fh)
        }
    for aposta in resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42):
        assert aposta.atualizado_em.strftime("%Y-%m-%d %H:%M:%S") > original[aposta.aposta_id]


def test_e_deterministico(lote_dia_1: Path) -> None:
    a = resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42)
    b = resolver_pendentes(lote_dia_1, DIA_1, DIA_2, seed=42)
    assert [(x.aposta_id, x.status, x.premio_pago) for x in a] == [
        (x.aposta_id, x.status, x.premio_pago) for x in b
    ]


def test_ignora_registros_defeituosos_do_lote_anterior(tmp_path: Path) -> None:
    """Aposta com campo obrigatório nulo já foi para a quarentena; não há
    status a resolver nela."""
    perfil = PerfilLote(
        data_lote=DIA_1,
        volume_apostas=1000,
        taxa_duplicadas=0.0,
        taxa_nulos=0.40,
        taxa_valor_invalido=0.0,
        taxa_data_posterior=0.0,
    )
    lote, _ = injetar(gerar_lote_valido(perfil), perfil)
    escrever_lote(lote, DIA_1, tmp_path)

    for aposta in resolver_pendentes(tmp_path, DIA_1, DIA_2, seed=42):
        assert aposta.aposta_id
        assert aposta.apostador_id
        assert aposta.evento_id
        assert aposta.data_aposta is not None
        assert aposta.valor_apostado is not None


def test_lote_anterior_ausente_falha_com_mensagem_clara(tmp_path: Path) -> None:
    with pytest.raises(LoteAnteriorAusenteError, match="lote anterior não encontrado"):
        resolver_pendentes(tmp_path, DIA_1, DIA_2, seed=42)


def test_identificadores_nao_colidem_entre_lotes(tmp_path: Path) -> None:
    """Regressão de um defeito real: os identificadores reiniciavam em zero a
    cada lote, então dois dias colidiam e um sobrescrevia o outro na
    deduplicação."""
    ids: dict[str, set[str]] = {}
    for dia in (DIA_1, DIA_2):
        perfil = PerfilLote(data_lote=dia, volume_apostas=200)
        lote = gerar_lote_valido(perfil)
        ids[dia.isoformat()] = {a.aposta_id for a in lote.apostas}
    assert not ids[DIA_1.isoformat()] & ids[DIA_2.isoformat()]
