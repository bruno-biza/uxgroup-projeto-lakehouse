"""Reprodutibilidade do gerador por checksum (SC-002, Princípio VI).

Este é o teste que sustenta a afirmação "dados sintéticos com seed fixa" da
constituição. Comparar amostras não serviria: só o checksum prova igualdade
byte a byte, que é o que permite ao avaliador ver exatamente os números
descritos na documentação.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from generator.config import PerfilLote
from generator.defeitos import injetar
from generator.entidades import gerar_lote_valido
from generator.escrita import escrever_lote

DATA = date(2026, 9, 10)
VOLUME = 800


def _gerar_em(destino: Path, seed: int = 42, volume: int = VOLUME) -> dict[str, str]:
    perfil = PerfilLote(data_lote=DATA, volume_apostas=volume, seed=seed)
    lote = gerar_lote_valido(perfil)
    lote, _ = injetar(lote, perfil)
    arquivos = escrever_lote(lote, DATA, destino)
    return {ent: dados["checksum"] for ent, dados in arquivos.items()}


def _sha256_do_arquivo(caminho: Path) -> str:
    return "sha256:" + hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_mesma_seed_produz_checksum_identico(tmp_path: Path) -> None:
    primeiro = _gerar_em(tmp_path / "a")
    segundo = _gerar_em(tmp_path / "b")
    assert primeiro == segundo, "mesma semente produziu arquivos diferentes"


def test_checksum_reportado_confere_com_o_arquivo(tmp_path: Path) -> None:
    """O checksum do log tem de ser o mesmo que um sha256sum externo daria.

    Se divergir, o valor publicado no log é inútil para conferência.
    """
    perfil = PerfilLote(data_lote=DATA, volume_apostas=VOLUME)
    lote = gerar_lote_valido(perfil)
    lote, _ = injetar(lote, perfil)
    arquivos = escrever_lote(lote, DATA, tmp_path)
    for dados in arquivos.values():
        assert dados["checksum"] == _sha256_do_arquivo(Path(dados["caminho"]))


def test_seed_diferente_produz_lote_diferente(tmp_path: Path) -> None:
    """Contraprova: se qualquer semente der o mesmo resultado, a semente é
    ignorada em algum ponto e o determinismo acima seria vazio."""
    assert _gerar_em(tmp_path / "a", seed=42) != _gerar_em(tmp_path / "b", seed=99)


def test_terminador_de_linha_e_sempre_lf(tmp_path: Path) -> None:
    """`\\r` no arquivo faria o checksum depender do sistema operacional."""
    perfil = PerfilLote(data_lote=DATA, volume_apostas=50)
    arquivos = escrever_lote(gerar_lote_valido(perfil), DATA, tmp_path)
    for dados in arquivos.values():
        assert b"\r" not in Path(dados["caminho"]).read_bytes()


def test_arquivo_nao_tem_bom(tmp_path: Path) -> None:
    """BOM apareceria como lixo na primeira coluna do COPY INTO."""
    perfil = PerfilLote(data_lote=DATA, volume_apostas=50)
    arquivos = escrever_lote(gerar_lote_valido(perfil), DATA, tmp_path)
    for dados in arquivos.values():
        assert not Path(dados["caminho"]).read_bytes().startswith(b"\xef\xbb\xbf")


def test_lote_vazio_escreve_somente_cabecalho(tmp_path: Path) -> None:
    """Caso de borda da spec: lote vazio é sucesso, não falha."""
    perfil = PerfilLote(data_lote=DATA, volume_apostas=0)
    arquivos = escrever_lote(gerar_lote_valido(perfil), DATA, tmp_path)
    conteudo = Path(arquivos["apostas"]["caminho"]).read_text(encoding="utf-8")
    assert conteudo.count("\n") == 1
    assert conteudo.startswith("aposta_id,")


def test_soma_das_taxas_acima_de_um_e_rejeitada() -> None:
    with pytest.raises(Exception, match="soma das taxas"):
        PerfilLote(
            data_lote=DATA,
            volume_apostas=100,
            taxa_duplicadas=0.5,
            taxa_nulos=0.5,
            taxa_valor_invalido=0.5,
            taxa_data_posterior=0.5,
        )


@pytest.mark.parametrize("taxa", [-0.1, 1.5])
def test_taxa_fora_do_intervalo_e_rejeitada(taxa: float) -> None:
    with pytest.raises(Exception, match=r"\[0, 1\]"):
        PerfilLote(data_lote=DATA, volume_apostas=100, taxa_nulos=taxa)
