"""Injeção dos quatro problemas de qualidade previstos na especificação.

Por que este módulo é separado de `entidades.py`: o lote válido tem de ser
gerável sozinho. Isso permite validar as métricas contra dado limpo antes de
introduzir sujeira, e depois atribuir qualquer rejeição observada a um defeito
que sabemos ter injetado. Misturar as duas coisas tornaria impossível
distinguir bug de métrica de efeito de defeito.

Duas propriedades deliberadas:

- **Seleção disjunta.** Os índices que recebem cada defeito são fatias
  distintas de uma única permutação. Sem isso, um registro poderia receber dois
  defeitos e a contagem por motivo não fecharia com a taxa pedida, tornando o
  cenário 4 do quickstart inconferível. Registros que violam várias regras
  ainda existem por sobreposição estatística — duplicata com nulo, por
  exemplo — e o pipeline os conta uma vez só, com vários motivos.
- **Semente derivada.** O `Random` daqui é semeado com `seed + 1`, e não com a
  semente do lote. Assim o núcleo válido é byte a byte o mesmo com ou sem
  injeção, o que torna possível comparar os dois lotes e isolar o efeito da
  sujeira.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import timedelta

from generator.config import PerfilLote
from generator.entidades import Aposta, Lote

# Campos obrigatórios candidatos a nulo, por entidade. A escolha de qual campo
# anular é sorteada para que a quarentena receba variedade de motivo, não
# sempre o mesmo campo.
CAMPOS_NULAVEIS_APOSTA = ("apostador_id", "evento_id", "data_aposta", "valor_apostado", "status")


def _contagem(taxa: float, total: int) -> int:
    """Número de registros a defeituar. Trunca, nunca arredonda para cima.

    Truncar mantém a garantia do contrato — tolerância de uma linha por
    defeito — e impede que a soma das taxas estoure o total quando várias
    taxas caem em fração.
    """
    return int(total * taxa)


def injetar(lote: Lote, perfil: PerfilLote) -> tuple[Lote, dict[str, int]]:
    """Suja o lote e devolve o lote resultante com a contagem efetiva por defeito.

    A contagem devolvida é o que o log da CLI publica e o que se confere contra
    `agg_qualidade_lote` — é a ponte entre o que foi injetado e o que o pipeline
    detectou.
    """
    rng = random.Random(perfil.seed + 1)
    apostas = list(lote.apostas)
    total = len(apostas)
    data_evento_por_id = {ev.evento_id: ev.data_evento for ev in lote.eventos}

    n_dup = _contagem(perfil.taxa_duplicadas, total)
    n_nulo = _contagem(perfil.taxa_nulos, total)
    n_valor = _contagem(perfil.taxa_valor_invalido, total)
    n_data = _contagem(perfil.taxa_data_posterior, total)

    indices = list(range(total))
    rng.shuffle(indices)
    corte_dup = indices[:n_dup]
    corte_nulo = indices[n_dup : n_dup + n_nulo]
    corte_valor = indices[n_dup + n_nulo : n_dup + n_nulo + n_valor]
    corte_data = indices[n_dup + n_nulo + n_valor : n_dup + n_nulo + n_valor + n_data]

    # --- Nulo em campo obrigatório -----------------------------------------
    for i in corte_nulo:
        campo = rng.choice(CAMPOS_NULAVEIS_APOSTA)
        apostas[i] = replace(apostas[i], **{campo: None})

    # --- Valor não positivo -------------------------------------------------
    # Zero e negativo são gerados em proporção parecida. Os dois violam a mesma
    # regra, mas são erros de origem diferentes na vida real, e a spec pede que
    # sejam contabilizados em separado — por isso ambos existem no lote.
    for i in corte_valor:
        apostas[i] = replace(
            apostas[i],
            valor_apostado=0.0 if rng.random() < 0.5 else -round(rng.uniform(1.0, 300.0), 2),
        )

    # --- Data de aposta posterior ao evento ---------------------------------
    for i in corte_data:
        aposta = apostas[i]
        data_evento = data_evento_por_id.get(aposta.evento_id)
        if data_evento is None:
            continue
        apostas[i] = replace(
            aposta, data_aposta=data_evento + timedelta(days=rng.randint(1, 5))
        )

    # --- Duplicata divergente ----------------------------------------------
    # Linhas ADICIONAIS com o mesmo aposta_id e atualizado_em mais recente. É o
    # caso que exercita a regra "vence o mais recente" de FR-005: a cópia nova
    # é a que deve sobreviver, e a original é a que vai para a quarentena.
    duplicatas: list[Aposta] = []
    for i in corte_dup:
        original = apostas[i]
        duplicatas.append(
            replace(
                original,
                valor_apostado=(
                    round(original.valor_apostado * rng.uniform(1.05, 1.5), 2)
                    if original.valor_apostado is not None
                    else None
                ),
                atualizado_em=original.atualizado_em + timedelta(seconds=rng.randint(1, 3600)),
            )
        )

    sujo = Lote(
        apostadores=lote.apostadores,
        eventos=lote.eventos,
        apostas=apostas + duplicatas,
        transacoes=lote.transacoes,
    )
    contagens = {
        "duplicata": len(duplicatas),
        "nulo_obrigatorio": len(corte_nulo),
        "valor_nao_positivo": len(corte_valor),
        "data_posterior_ao_evento": len(corte_data),
    }
    return sujo, contagens
