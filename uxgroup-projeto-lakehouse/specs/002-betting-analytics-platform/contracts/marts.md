# Contrato — tabelas de métricas (MARTS)

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11

Este é o contrato voltado ao consumidor: analista de negócio, time financeiro e engenheiro de dados
leem estas tabelas em `BETS.MARTS`. Cada tabela declara o que inclui e o que **não** inclui, como
`FR-017` exige. O texto da coluna "não inclui" é o que vai para `docs/metricas.md` e para as
descrições no `schema.yml` do dbt.

---

## `agg_ggr_diario_esporte` — US1

**Grão**: uma linha por `data_aposta` × `esporte`. Chave composta única e não nula.

| Coluna | Tipo | Definição |
|---|---|---|
| `data_aposta` | `DATE` | Data em que a aposta foi feita, não a data do evento |
| `esporte` | `VARCHAR` | Esporte do evento apostado |
| `total_apostado` | `NUMBER(14,2)` | Soma de `valor_apostado` das apostas com status `ganha` ou `perdida` |
| `premios_pagos` | `NUMBER(14,2)` | Soma de `premio_pago` das mesmas apostas |
| `ggr` | `NUMBER(14,2)` | `total_apostado - premios_pagos`. **Pode ser negativo** |
| `exposicao_pendente` | `NUMBER(14,2)` | Soma de `valor_apostado` das apostas `pendente` da mesma data e esporte |
| `qtd_apostas_resolvidas` | `NUMBER` | Contagem das apostas que entraram no GGR |

**Inclui**: apenas apostas válidas — aprovadas em todas as regras de qualidade — com status `ganha`
ou `perdida`.

**Não inclui**: apostas `cancelada` (o valor é devolvido, não há receita); apostas `pendente` nas
três colunas de receita (elas aparecem só em `exposicao_pendente`); nenhum registro em quarentena;
nenhum custo operacional, imposto ou bônus — GGR é receita bruta de jogo, não lucro.

**Nunca faça**: somar `ggr` com `exposicao_pendente`. São grandezas de naturezas diferentes — uma é
receita realizada, a outra é dinheiro em risco ainda não resolvido. A separação foi uma decisão
explícita registrada em [spec.md § Clarifications](../spec.md#clarifications).

**Volatilidade**: o `ggr` de uma data passada **muda** quando uma aposta daquela data sai de
`pendente` (`FR-019b`). A tabela é sempre a melhor leitura disponível, não um fechamento contábil.

---

## `agg_engajamento_diario` — US3

**Grão**: uma linha por `data_aposta`. Chave única e não nula.

| Coluna | Tipo | Definição |
|---|---|---|
| `data_aposta` | `DATE` | Data da aposta |
| `volume_apostado` | `NUMBER(14,2)` | Soma de `valor_apostado` de todas as apostas válidas, incluindo `pendente` e `cancelada` |
| `ticket_medio` | `NUMBER(12,2)` | `volume_apostado / qtd_apostas`. **Nulo**, nunca zero, quando `qtd_apostas = 0` |
| `apostadores_ativos` | `NUMBER` | Contagem distinta de `apostador_id` com ao menos uma aposta válida na data |
| `qtd_apostas` | `NUMBER` | Contagem de apostas válidas |

**Inclui**: todas as apostas válidas, independentemente de status — esta é uma métrica de atividade,
não de receita, e por isso o critério difere do GGR de propósito.

**Não inclui**: registros em quarentena; apostadores sem aposta na data (não são "ativos"); número
de acessos, sessões ou logins — não há esse dado no escopo.

**Atenção**: `volume_apostado` daqui **não** é comparável a `total_apostado` de
`agg_ggr_diario_esporte`, porque aquele exclui pendentes e canceladas e este não. Comparar os dois
sem essa ressalva é o erro de leitura mais provável destas tabelas.

---

## `agg_financeiro_diario` — US4

**Grão**: uma linha por `data_transacao`. Chave única e não nula.

| Coluna | Tipo | Definição |
|---|---|---|
| `data_transacao` | `DATE` | Data do movimento financeiro |
| `total_depositado` | `NUMBER(14,2)` | Soma dos valores com `tipo = 'deposito'` |
| `total_sacado` | `NUMBER(14,2)` | Soma dos valores com `tipo = 'saque'` |
| `liquido` | `NUMBER(14,2)` | `total_depositado - total_sacado`. **Pode ser negativo** |
| `qtd_depositos`, `qtd_saques` | `NUMBER` | Contagens por tipo |

**Inclui**: transações válidas de depósito e saque.

**Não inclui**: saldo de conta de apostador (não é modelado); estornos e chargebacks (fora do
escopo); qualquer relação com o GGR — dinheiro movimentado e receita de jogo são coisas distintas e
não se reconciliam entre si.

---

## `agg_qualidade_lote` — US2

**Grão**: uma linha por `lote_data` × `entidade` × `motivo`. Chave composta única e não nula.

| Coluna | Tipo | Definição |
|---|---|---|
| `lote_data` | `DATE` | Lote processado |
| `entidade` | `VARCHAR` | `apostadores`, `eventos`, `apostas` ou `transacoes` |
| `motivo` | `VARCHAR` | Motivo do descarte; conjunto fechado do catálogo em [data-model.md](../data-model.md) |
| `qtd_recebidos` | `NUMBER` | Linhas recebidas em RAW para a entidade no lote |
| `qtd_aceitos` | `NUMBER` | Linhas que chegaram ao modelo limpo |
| `qtd_rejeitados` | `NUMBER` | Linhas em quarentena por aquele motivo |
| `taxa_rejeicao` | `NUMBER(5,4)` | `qtd_rejeitados / qtd_recebidos` da entidade |

**Invariante testado**: por `lote_data` e `entidade`, `qtd_recebidos = qtd_aceitos + total de
rejeitados distintos`. Um registro com vários motivos aparece em mais de uma linha de motivo, mas
conta **uma vez** no total de rejeitados distintos — é por isso que o invariante compara contagem
distinta, e não a soma de `qtd_rejeitados` por motivo. Isso é `SC-005`.

**Comportamento em taxa alta**: nenhuma taxa, nem 100%, interrompe a execução (`FR-016a`). A tabela
reporta; ela não bloqueia. O que bloqueia é teste estrutural (`FR-020`).

**Rastro até o registro**: `qua_registros_rejeitados` em `BETS.STAGING` guarda o registro original em
`VARIANT`, com `arquivo_origem`, `linha_origem` e o array de motivos — o caminho de volta até a
linha do CSV (`FR-010`, `SC-004`).

---

## Garantias transversais

1. **Nenhum registro inválido em nenhuma destas tabelas** (`FR-011`, `SC-003`), garantido por teste
   singular que varre as regras de qualidade contra os fatos.
2. **Reprocessar não muda valor** (`SC-002`): teste de dupla execução compara contagens e somas.
3. **Nenhuma métrica parcial visível após falha** (`SC-010`), com a ressalva de que `fct_apostas`
   pode ficar à frente dos agregados — ver [research.md § D3](../research.md#d3).
4. **Toda tabela declara inclusão e exclusão** (`FR-017`), replicado no `schema.yml` do dbt para que
   a documentação gerada carregue o mesmo texto.
