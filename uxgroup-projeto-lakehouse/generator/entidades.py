"""Geração das entidades válidas do lote.

Por que este módulo existe: separa a construção do dado correto da injeção de
defeitos (`generator/defeitos.py`). A separação não é estética — ela permite
gerar um lote 100% válido para validar as métricas e, só depois, sujá-lo para
validar a quarentena. Se as duas coisas estivessem no mesmo lugar, não haveria
como saber se um número errado veio da métrica ou do defeito.

Determinismo (Princípio VI): todo sorteio passa por uma única instância de
`random.Random` semeada, nunca pelo `random` do módulo. O `random` global é
estado compartilhado do processo — qualquer biblioteca que o use muda o
resultado, e o checksum deixa de bater sem que nada no nosso código tenha
mudado.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from faker import Faker

from generator.config import (
    ANCORA_CADASTRO,
    CAMPEONATOS,
    ESPORTES,
    ESTADOS,
    PESOS_STATUS,
    TIMES,
    TIPOS_TRANSACAO,
    PerfilLote,
)


@dataclass
class Apostador:
    apostador_id: str
    criado_em: date
    estado: str
    atualizado_em: datetime


@dataclass
class Evento:
    evento_id: str
    esporte: str
    campeonato: str
    time_casa: str
    time_visitante: str
    data_evento: date
    atualizado_em: datetime


@dataclass
class Aposta:
    aposta_id: str
    apostador_id: str
    evento_id: str
    data_aposta: date
    valor_apostado: float
    odd: float
    status: str
    premio_pago: float
    atualizado_em: datetime


@dataclass
class Transacao:
    transacao_id: str
    apostador_id: str
    data_transacao: date
    tipo: str
    valor: float
    atualizado_em: datetime


@dataclass
class Lote:
    """Conjunto completo de um dia. É o que a escrita consome."""

    apostadores: list[Apostador]
    eventos: list[Evento]
    apostas: list[Aposta]
    transacoes: list[Transacao]


def _instante(rng: random.Random, dia: date) -> datetime:
    """Timestamp de atualização dentro do dia, em UTC.

    Tudo no pipeline é UTC (decisão D7): elimina o caso de borda da fronteira de
    dia por construção, em vez de resolvê-lo com regra documentada.
    """
    return datetime.combine(dia, datetime.min.time()) + timedelta(seconds=rng.randrange(0, 86_400))


def _sortear_status(rng: random.Random) -> str:
    """Sorteio ponderado dos status, com pesos de `config.PESOS_STATUS`."""
    return rng.choices(list(PESOS_STATUS), weights=list(PESOS_STATUS.values()), k=1)[0]


def gerar_apostadores(perfil: PerfilLote, rng: random.Random, faker: Faker) -> list[Apostador]:
    """Apostadores fictícios.

    Nenhum campo carrega dado pessoal real (Princípio VI): não há nome, e-mail,
    documento nem data de nascimento. `estado` é a única informação
    demográfica, e é uma sigla de UF de conjunto fechado.

    O identificador e o conteúdo são ESTÁVEIS entre lotes de propósito: o mesmo
    apostador aposta em vários dias, e é isso que dá sentido a contá-lo uma vez
    por dia em `apostadores_ativos`. Por isso `criado_em` é ancorado numa data
    fixa e não na data do lote — se dependesse do lote, o mesmo apostador teria
    cadastro diferente a cada dia e a deduplicação entre lotes ficaria sem
    significado.
    """
    apostadores: list[Apostador] = []
    for i in range(perfil.volume_apostadores):
        criado_em = faker.date_between_dates(
            date_start=ANCORA_CADASTRO,
            date_end=ANCORA_CADASTRO + timedelta(days=730),
        )
        apostadores.append(
            Apostador(
                apostador_id=f"APT{i:07d}",
                criado_em=criado_em,
                estado=rng.choice(ESTADOS),
                atualizado_em=datetime.combine(criado_em, datetime.min.time()),
            )
        )
    return apostadores


def gerar_eventos(perfil: PerfilLote, rng: random.Random) -> list[Evento]:
    """Eventos esportivos.

    `time_casa` e `time_visitante` são obrigatoriamente diferentes: é regra de
    negócio e é testada em STAGING, então gerar um evento de um time contra si
    mesmo produziria uma rejeição que não corresponde a nenhum defeito injetado
    de propósito — ruído que atrapalharia a conferência da US2.

    A data do evento pode ser anterior ou posterior à data do lote. Evento
    futuro é o que dá sentido à aposta pendente.
    """
    eventos: list[Evento] = []
    for i in range(perfil.volume_eventos):
        esporte = rng.choice(ESPORTES)
        casa, visitante = rng.sample(TIMES[esporte], 2)
        eventos.append(
            Evento(
                evento_id=f"EVT{perfil.data_lote:%Y%m%d}{i:05d}",
                esporte=esporte,
                campeonato=rng.choice(CAMPEONATOS[esporte]),
                time_casa=casa,
                time_visitante=visitante,
                data_evento=perfil.data_lote + timedelta(days=rng.randint(-10, 15)),
                atualizado_em=_instante(rng, perfil.data_lote),
            )
        )
    return eventos


def gerar_apostas(
    perfil: PerfilLote, eventos: list[Evento], apostadores: list[Apostador], rng: random.Random
) -> list[Aposta]:
    """Apostas válidas.

    Invariantes respeitados aqui, todos testados depois em STAGING:

    - `data_aposta <= data_evento` — não se aposta em evento já ocorrido;
    - `valor_apostado > 0` e `odd >= 1`;
    - `premio_pago = 0` obrigatoriamente quando o status não é `ganha`;
    - `premio_pago = valor_apostado * odd` quando é `ganha`.

    A última é o que faz o GGR ser negativo em alguns dias: com odd média acima
    de 2, um dia com muitas apostas ganhas custa mais do que arrecada. Isso é
    realista e exercita o requisito de que o GGR pode ser negativo sem truncar.
    """
    apostas: list[Aposta] = []
    for i in range(perfil.volume_apostas):
        evento = rng.choice(eventos)
        apostador = rng.choice(apostadores)

        # A aposta acontece entre 10 dias antes do evento e a data do evento,
        # nunca depois. Se o evento já passou em relação ao lote, a aposta é
        # ancorada na data do evento.
        limite = min(evento.data_evento, perfil.data_lote)
        inicio = limite - timedelta(days=10)
        data_aposta = inicio + timedelta(days=rng.randint(0, (limite - inicio).days))

        valor = round(rng.uniform(5.0, 500.0), 2)
        odd = round(rng.uniform(1.2, 8.0), 2)
        status = _sortear_status(rng)
        premio = round(valor * odd, 2) if status == "ganha" else 0.0

        apostas.append(
            Aposta(
                aposta_id=f"APS{perfil.data_lote:%Y%m%d}{i:07d}",
                apostador_id=apostador.apostador_id,
                evento_id=evento.evento_id,
                data_aposta=data_aposta,
                valor_apostado=valor,
                odd=odd,
                status=status,
                premio_pago=premio,
                atualizado_em=_instante(rng, perfil.data_lote),
            )
        )
    return apostas


def gerar_transacoes(
    perfil: PerfilLote, apostadores: list[Apostador], rng: random.Random
) -> list[Transacao]:
    """Depósitos e saques válidos.

    Os saques usam faixa de valor maior que os depósitos de propósito, para que
    o líquido diário seja negativo em parte dos dias — o cenário que o teste de
    `agg_financeiro_diario` precisa exercitar.
    """
    transacoes: list[Transacao] = []
    for i in range(perfil.volume_transacoes):
        tipo = rng.choice(TIPOS_TRANSACAO)
        valor = (
            round(rng.uniform(20.0, 800.0), 2)
            if tipo == "deposito"
            else round(rng.uniform(50.0, 1500.0), 2)
        )
        transacoes.append(
            Transacao(
                transacao_id=f"TRX{perfil.data_lote:%Y%m%d}{i:07d}",
                apostador_id=rng.choice(apostadores).apostador_id,
                data_transacao=perfil.data_lote,
                tipo=tipo,
                valor=valor,
                atualizado_em=_instante(rng, perfil.data_lote),
            )
        )
    return transacoes


def gerar_lote_valido(perfil: PerfilLote) -> Lote:
    """Monta o lote completo, sem nenhum defeito injetado.

    A semente única do perfil alimenta tanto o `Random` local quanto o `Faker`.
    Semear só um dos dois deixaria metade do lote variando entre execuções.
    """
    rng = random.Random(perfil.seed)
    faker = Faker("pt_BR")
    faker.seed_instance(perfil.seed)

    apostadores = gerar_apostadores(perfil, rng, faker)
    eventos = gerar_eventos(perfil, rng)
    apostas = gerar_apostas(perfil, eventos, apostadores, rng)
    transacoes = gerar_transacoes(perfil, apostadores, rng)

    return Lote(apostadores=apostadores, eventos=eventos, apostas=apostas, transacoes=transacoes)
