"""Perfil de um lote diário sintético.

Por que este módulo existe: as proporções entre entidades e as taxas de defeito
são parâmetros de negócio, não constantes espalhadas pelo código de geração.
Reuni-las num objeto congelado torna o lote inteiramente descrito por um valor,
que é o que permite reproduzir uma execução a partir do log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Padrões do contrato da CLI (contracts/cli.md). Somam 12% de sujeira, que é
# proporção suficiente para a quarentena ser visível numa demo sem que os
# agregados percam sentido.
SEED_PADRAO = 42

# Âncora fixa para a data de criação de conta dos apostadores. Precisa ser
# independente da data do lote: o mesmo apostador aparece em vários lotes, e se
# o cadastro dele mudasse a cada dia a deduplicação entre lotes ficaria sem
# significado.
ANCORA_CADASTRO = date(2024, 1, 1)

# Fração das apostas pendentes de um lote anterior que são resolvidas quando o
# gerador recebe --resolver-pendentes-de. Nem todas, porque evento futuro
# continua pendente — é o que mantém a coluna de exposição pendente com
# conteúdo.
FRACAO_PENDENTES_RESOLVIDAS = 0.6
TAXA_DUPLICADAS_PADRAO = 0.05
TAXA_NULOS_PADRAO = 0.03
TAXA_VALOR_INVALIDO_PADRAO = 0.02
TAXA_DATA_POSTERIOR_PADRAO = 0.02

# Conjuntos fechados. O mesmo domínio é testado com accepted_values no dbt; se
# divergirem, o teste de dados reprova — que é o comportamento desejado.
ESPORTES = ("futebol", "basquete", "tenis", "volei", "mma")

CAMPEONATOS = {
    "futebol": ("Brasileirao Serie A", "Copa do Brasil", "Libertadores"),
    "basquete": ("NBB", "NBA"),
    "tenis": ("ATP Masters", "Roland Garros"),
    "volei": ("Superliga",),
    "mma": ("UFC",),
}

TIMES = {
    "futebol": (
        "Flamengo", "Palmeiras", "Corinthians", "Sao Paulo", "Gremio",
        "Internacional", "Atletico-MG", "Fluminense", "Botafogo", "Santos",
    ),
    "basquete": ("Franca", "Flamengo Basquete", "Minas", "Pinheiros", "Lakers", "Celtics"),
    "tenis": ("Alcaraz", "Djokovic", "Sinner", "Medvedev", "Zverev", "Rune"),
    "volei": ("Sada Cruzeiro", "Praia Clube", "Minas Volei", "Sesi-SP"),
    "mma": ("Lutador A", "Lutador B", "Lutador C", "Lutador D"),
}

ESTADOS = (
    "AC", "AL", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MG",
    "MS", "MT", "PA", "PB", "PE", "PR", "RJ", "RN", "RS", "SC",
    "SE", "SP", "TO",
)

STATUS_APOSTA = ("ganha", "perdida", "pendente", "cancelada")

TIPOS_TRANSACAO = ("deposito", "saque")

# Distribuição de status. Pendentes precisam ser frequentes o bastante para que
# a coluna de exposição pendente tenha conteúdo e para que o cenário de
# resolução em lote posterior seja demonstrável.
PESOS_STATUS = {"ganha": 0.28, "perdida": 0.52, "pendente": 0.15, "cancelada": 0.05}


class PerfilInvalidoError(ValueError):
    """Parâmetros de lote fora do domínio aceito."""


@dataclass(frozen=True)
class PerfilLote:
    """Descrição completa de um lote a gerar."""

    data_lote: date
    volume_apostas: int
    seed: int = SEED_PADRAO
    taxa_duplicadas: float = TAXA_DUPLICADAS_PADRAO
    taxa_nulos: float = TAXA_NULOS_PADRAO
    taxa_valor_invalido: float = TAXA_VALOR_INVALIDO_PADRAO
    taxa_data_posterior: float = TAXA_DATA_POSTERIOR_PADRAO

    def __post_init__(self) -> None:
        if self.volume_apostas < 0:
            raise PerfilInvalidoError("volume deve ser maior ou igual a zero")
        for nome, taxa in self.taxas.items():
            if not 0.0 <= taxa <= 1.0:
                raise PerfilInvalidoError(f"{nome} deve estar em [0, 1]; recebido {taxa}")
        soma = sum(self.taxas.values())
        if soma > 1.0:
            raise PerfilInvalidoError(
                f"a soma das taxas de defeito não pode passar de 1.0; recebido {soma:.4f}"
            )

    @property
    def taxas(self) -> dict[str, float]:
        return {
            "taxa_duplicadas": self.taxa_duplicadas,
            "taxa_nulos": self.taxa_nulos,
            "taxa_valor_invalido": self.taxa_valor_invalido,
            "taxa_data_posterior": self.taxa_data_posterior,
        }

    # As demais entidades são dimensionadas a partir do volume de apostas, para
    # que um único parâmetro controle o tamanho do lote.
    @property
    def volume_apostadores(self) -> int:
        """Cerca de 10 apostas por apostador — dá repetição suficiente para que
        `apostadores_ativos` seja menor que `qtd_apostas` e a contagem distinta
        tenha o que provar."""
        return max(1, self.volume_apostas // 10)

    @property
    def volume_eventos(self) -> int:
        """Cerca de 60 apostas por evento."""
        return max(1, self.volume_apostas // 60)

    @property
    def volume_transacoes(self) -> int:
        return max(1, self.volume_apostas // 4)
