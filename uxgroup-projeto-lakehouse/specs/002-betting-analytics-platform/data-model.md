# Phase 1 — Data Model: Plataforma Analítica de Apostas Esportivas

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11 | **Plan**: [plan.md](./plan.md)

Três camadas no database `BETS`. Cada camada lê apenas da anterior (Princípio III). Os tipos são do
dialeto Snowflake.

---

## Camada RAW — o dado como chegou

Todas as colunas de negócio são `VARCHAR`, sem exceção: RAW não tipa, não converte e não valida
(`FR-004`). O `COPY INTO` nunca falha por conteúdo malformado, porque não há conversão a falhar — é
o que permite que um registro com valor negativo ou data impossível chegue intacto à quarentena em
vez de matar a carga.

Colunas de metadados presentes nas quatro tabelas:

| Coluna | Tipo | Origem |
|---|---|---|
| `arquivo_origem` | `VARCHAR` | `METADATA$FILENAME` do `COPY INTO` |
| `linha_origem` | `NUMBER` | `METADATA$FILE_ROW_NUMBER` |
| `carregado_em` | `TIMESTAMP_NTZ` | `CURRENT_TIMESTAMP()` no momento da carga |
| `lote_data` | `DATE` | parâmetro da execução, não data corrente |

`lote_data` é a chave de substituição da decisão [D1](./research.md#d1): a carga apaga
`WHERE lote_data = :data` antes de recarregar.

**Tabelas**: `raw_apostadores`, `raw_eventos`, `raw_apostas`, `raw_transacoes`. As colunas de
negócio de cada uma são as do contrato do CSV — ver
[contracts/csv-batch.md](./contracts/csv-batch.md).

---

## Camada STAGING — limpo, tipado, e o que sobrou

Cada entidade produz **dois** modelos: o limpo e a quarentena. A soma das linhas dos dois é igual ao
número de linhas recebidas em RAW para aquele lote — é o invariante que `SC-005` mede.

### Modelos limpos

**`stg_apostadores`**

| Coluna | Tipo | Regra |
|---|---|---|
| `apostador_id` | `VARCHAR` | chave, única, não nula |
| `criado_em` | `DATE` | não nula |
| `estado` | `VARCHAR(2)` | sigla de UF, conjunto fechado |
| `atualizado_em` | `TIMESTAMP_NTZ` | define a versão canônica ([D6](./research.md)) |
| `lote_data` | `DATE` | proveniência |

**`stg_eventos`**

| Coluna | Tipo | Regra |
|---|---|---|
| `evento_id` | `VARCHAR` | chave, única, não nula |
| `esporte` | `VARCHAR` | conjunto fechado, não nulo |
| `campeonato` | `VARCHAR` | não nulo |
| `time_casa`, `time_visitante` | `VARCHAR` | não nulos e diferentes entre si |
| `data_evento` | `DATE` | não nula |
| `atualizado_em` | `TIMESTAMP_NTZ` | versão canônica |
| `lote_data` | `DATE` | proveniência |

**`stg_apostas`** — entidade central

| Coluna | Tipo | Regra |
|---|---|---|
| `aposta_id` | `VARCHAR` | chave, única, não nula |
| `apostador_id` | `VARCHAR` | FK para `stg_apostadores`, não nula |
| `evento_id` | `VARCHAR` | FK para `stg_eventos`, não nula |
| `data_aposta` | `DATE` | não nula, `<= data_evento` |
| `valor_apostado` | `NUMBER(12,2)` | não nulo, `> 0` |
| `odd` | `NUMBER(8,2)` | não nula, `>= 1` |
| `status` | `VARCHAR` | um de `ganha`, `perdida`, `pendente`, `cancelada` |
| `premio_pago` | `NUMBER(12,2)` | `>= 0`; obrigatoriamente `0` quando o status não é `ganha` |
| `atualizado_em` | `TIMESTAMP_NTZ` | versão canônica |
| `lote_data` | `DATE` | proveniência |

**`stg_transacoes`**

| Coluna | Tipo | Regra |
|---|---|---|
| `transacao_id` | `VARCHAR` | chave, única, não nula |
| `apostador_id` | `VARCHAR` | FK para `stg_apostadores`, não nula |
| `data_transacao` | `DATE` | não nula |
| `tipo` | `VARCHAR` | `deposito` ou `saque` |
| `valor` | `NUMBER(12,2)` | não nulo, `> 0` |
| `atualizado_em` | `TIMESTAMP_NTZ` | versão canônica |
| `lote_data` | `DATE` | proveniência |

### Modelos de quarentena

`stg_apostadores_rejeitadas`, `stg_eventos_rejeitadas`, `stg_apostas_rejeitadas`,
`stg_transacoes_rejeitadas` — esquema idêntico entre si:

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `entidade` | `VARCHAR` | nome da entidade de origem |
| `chave_natural` | `VARCHAR` | identificador quando legível; nulo se o próprio id veio nulo |
| `registro_original` | `VARIANT` | o registro de RAW inteiro, como chegou (`FR-010`) |
| `motivos` | `ARRAY` | todos os motivos aplicáveis, não apenas o primeiro |
| `arquivo_origem`, `linha_origem` | `VARCHAR`, `NUMBER` | rastro até a linha do CSV |
| `lote_data` | `DATE` | lote de origem |
| `rejeitado_em` | `TIMESTAMP_NTZ` | momento do descarte |

A view `qua_registros_rejeitados` é o `UNION ALL` das quatro e é a única fonte de
`agg_qualidade_lote`.

### Catálogo de motivos de rejeição

Conjunto fechado — `accepted_values` testa a coluna quando desaninhada:

| Motivo | Regra violada | Requisito |
|---|---|---|
| `duplicata` | Perdeu a disputa por `atualizado_em` dentro do lote | `FR-005` |
| `nulo_obrigatorio` | Campo obrigatório nulo ou vazio | `FR-006` |
| `valor_nao_positivo` | `valor_apostado <= 0` (zero e negativo contados em separado pelo campo `detalhe`) | `FR-007` |
| `data_posterior_ao_evento` | `data_aposta > data_evento` | `FR-008` |
| `apostador_inexistente` | FK sem correspondência | `FR-009` |
| `evento_inexistente` | FK sem correspondência | `FR-009` |
| `premio_inconsistente` | `premio_pago <> 0` em status diferente de `ganha` | premissa da spec |
| `status_invalido` | Fora do conjunto fechado | `FR-012` |

Um registro que viola várias regras aparece **uma vez**, com vários itens em `motivos` — o caso de
borda do cenário 4 da US2.

---

## Camada MARTS — métricas de negócio

### Dimensões

**`dim_apostadores`** — `apostador_id` (chave), `criado_em`, `estado`, `antiguidade_dias`.
**`dim_eventos`** — `evento_id` (chave), `esporte`, `campeonato`, `time_casa`, `time_visitante`,
`data_evento`.

Materialização: tabela full-refresh. O volume não justifica outra coisa.

### Fatos

**`fct_apostas`** — incremental, `unique_key = 'aposta_id'`, `incremental_strategy = 'merge'`.

Colunas: `aposta_id`, `apostador_id`, `evento_id`, `data_aposta`, `esporte`, `valor_apostado`,
`odd`, `status`, `premio_pago`, `resultado_casa` (`valor_apostado - premio_pago`, nulo quando não
resolvida), `atualizado_em`, `lote_data`.

O `merge` por `aposta_id` é o que implementa `FR-019a`: a aposta que volta num lote posterior com
status final substitui a versão anterior em vez de criar linha nova. `esporte` é desnormalizado a
partir de `dim_eventos` para que `agg_ggr_diario_esporte` não precise de join — decisão de
simplicidade, não de performance.

**`fct_transacoes`** — incremental, `unique_key = 'transacao_id'`, estratégia `merge`. Colunas:
`transacao_id`, `apostador_id`, `data_transacao`, `tipo`, `valor`, `atualizado_em`, `lote_data`.

### Agregados diários

Todos full-refresh, pelo motivo da decisão [D2](./research.md). Contrato completo em
[contracts/marts.md](./contracts/marts.md).

**`agg_ggr_diario_esporte`** (`FR-013`, `FR-013a`) — grão: `data_aposta` × `esporte`.

| Coluna | Definição |
|---|---|
| `total_apostado` | soma de `valor_apostado` onde status ∈ (`ganha`, `perdida`) |
| `premios_pagos` | soma de `premio_pago` onde status ∈ (`ganha`, `perdida`) |
| `ggr` | `total_apostado - premios_pagos` — pode ser negativo |
| `exposicao_pendente` | soma de `valor_apostado` onde status = `pendente`, **nunca somada ao GGR** |
| `qtd_apostas_resolvidas` | contagem das apostas que entraram no GGR |

**`agg_engajamento_diario`** (`FR-014`) — grão: `data_aposta`.
`volume_apostado`, `ticket_medio` (nulo, não zero, quando não há aposta válida),
`apostadores_ativos` (contagem distinta), `qtd_apostas`.

**`agg_financeiro_diario`** (`FR-015`) — grão: `data_transacao`.
`total_depositado`, `total_sacado`, `liquido` (`depositado - sacado`, pode ser negativo),
`qtd_depositos`, `qtd_saques`.

**`agg_qualidade_lote`** (`FR-016`, `FR-016a`) — grão: `lote_data` × `entidade` × `motivo`.
`qtd_recebidos`, `qtd_aceitos`, `qtd_rejeitados`, `taxa_rejeicao`. A taxa é informativa e nunca
interrompe a execução.

---

## Transições de estado da aposta

```text
pendente ──► ganha       (premio_pago > 0)
         ├─► perdida     (premio_pago = 0)
         └─► cancelada   (premio_pago = 0, fora do GGR)
```

Só `pendente` é estado de partida. A transição chega num lote posterior trazendo o mesmo
`aposta_id` com `atualizado_em` mais recente; o `merge` substitui a versão e, por serem
full-refresh, os agregados da `data_aposta` original passam a refletir o novo status — `FR-019b`
sem código de backfill. Transição para trás (resolvida voltando a pendente) não é gerada e, se
aparecer, perde por `atualizado_em` ou é aceita como último estado conhecido; não é tratada como
erro porque não há regra de negócio para isso em dado sintético.

---

## Cobertura dos requisitos

| Requisito | Onde é satisfeito |
|---|---|
| `FR-004` preservar como recebido | RAW, todas as colunas `VARCHAR` |
| `FR-005`, `FR-005a` duplicatas | `atualizado_em` + `ROW_NUMBER()` nos modelos limpos |
| `FR-006` a `FR-009` validações | modelos de quarentena, catálogo de motivos |
| `FR-010` rastreabilidade | `registro_original VARIANT` + `motivos ARRAY` |
| `FR-011` inválido fora das métricas | quarentena é tabela separada, não flag |
| `FR-012` padronização | tipagem e conjuntos fechados em STAGING |
| `FR-013`, `FR-013a` | `agg_ggr_diario_esporte` |
| `FR-014` | `agg_engajamento_diario` |
| `FR-015` | `agg_financeiro_diario` |
| `FR-016`, `FR-016a` | `agg_qualidade_lote` |
| `FR-019a`, `FR-019b` | `merge` nos fatos + agregados full-refresh |
| `SC-005` recebidos = aceitos + rejeitados | teste singular sobre STAGING vs RAW |
