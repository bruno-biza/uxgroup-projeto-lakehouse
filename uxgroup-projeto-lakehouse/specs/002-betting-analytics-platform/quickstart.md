# Quickstart — validação ponta a ponta

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11 | **Plan**: [plan.md](./plan.md)

Roteiro executável que prova que a feature funciona. Cada cenário fecha num critério de sucesso da
[spec](./spec.md). Este documento é também a espinha do ensaio da demo: os cenários 1, 4 e 5 são o
que se mostra ao vivo.

## Pré-requisitos

| Item | Versão | Observação |
|---|---|---|
| Docker + Docker Compose | Engine 24+ | Airflow e Postgres sobem aqui |
| Python | 3.11 | Para rodar gerador e testes fora do contêiner |
| Conta trial do Snowflake | — | Gratuita, 30 dias. Nenhum upgrade (Princípio I) |
| Memória livre | ~4 GB | Airflow com scheduler e webserver |

## Configuração

```bash
cp .env.example .env
# preencher SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
```

`.env` está no `.gitignore` e nunca é versionado (Princípio VIII). Confirme antes de qualquer
commit:

```bash
git check-ignore .env   # deve imprimir: .env
```

## Bootstrap, uma vez

```bash
make setup      # aplica snowflake_setup/*.sql: warehouse XSMALL, database BETS, schemas, stage, DDL de RAW
make up         # sobe Postgres + Airflow (build da imagem com o venv do dbt na primeira vez)
```

Verificação: `make setup` é idempotente — rodar de novo não deve dar erro nem recriar objeto
(`CREATE ... IF NOT EXISTS`). A UI do Airflow responde em `http://localhost:8080`.

---

## Cenário 1 — Um lote novo atravessa o pipeline (`SC-001`, `SC-006`)

```bash
make run DATA=2026-09-10
```

Dispara a DAG `pipeline_bets` para a data lógica, com as seis tarefas em sequência:
`gerar_lote → carregar_raw → dbt_run_staging → dbt_test_staging → dbt_run_marts → dbt_test_marts`.

**Esperado**: todas as tarefas verdes, nenhuma intervenção manual entre elas, duração total abaixo
de 5 minutos. Depois:

```sql
SELECT data_aposta, esporte, total_apostado, premios_pagos, ggr, exposicao_pendente
FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE
WHERE data_aposta = '2026-09-10'
ORDER BY ggr DESC;
```

**Esperado**: uma linha por esporte, `ggr = total_apostado - premios_pagos` em todas, e
`exposicao_pendente` preenchida sem ter sido somada ao GGR. Uma consulta responde "qual foi o GGR de
ontem por esporte" — é `SC-006`.

---

## Cenário 2 — Reprocessar não altera nada (`SC-002`, `FR-019`)

```bash
make run DATA=2026-09-10      # segunda vez, mesma data
pytest tests/integration/test_idempotencia.py -v
```

O teste captura contagens e somas de RAW, STAGING e MARTS antes e depois e exige igualdade exata.

**Esperado**: variação zero em todos os campos comparados. Se `raw_apostas` crescer, a substituição
por lote da decisão [D1](./research.md#d1) não está funcionando — é a falha mais importante a
detectar aqui.

Vale repetir com parâmetros diferentes, que é o caso que o histórico de carga do `COPY INTO` não
cobre sozinho:

```bash
make run DATA=2026-09-10 VOLUME=30000    # mesma data, conteúdo diferente
```

**Esperado**: RAW reflete apenas o último lote daquela data, sem soma das duas gerações.

---

## Cenário 3 — Determinismo do gerador (`SC-002`, Princípio VI)

```bash
pytest tests/unit/test_determinismo.py -v
```

Gera o mesmo lote duas vezes com a mesma semente em diretórios distintos e compara checksum
SHA-256 arquivo por arquivo.

**Esperado**: checksums idênticos. Falha aqui costuma ser `\r\n` em Windows ou iteração sobre
estrutura não ordenada ([D5](./research.md)).

---

## Cenário 4 — Nada inválido nas métricas, tudo rastreável (`SC-003`, `SC-004`, `SC-005`)

```sql
-- Resumo de qualidade do lote
SELECT entidade, motivo, qtd_rejeitados, taxa_rejeicao
FROM BETS.MARTS.AGG_QUALIDADE_LOTE
WHERE lote_data = '2026-09-10'
ORDER BY qtd_rejeitados DESC;
```

**Esperado**: os quatro motivos injetados presentes, com contagens compatíveis com as taxas
passadas ao gerador (o log de `gerar_lote` traz a contagem efetiva para conferir).

```sql
-- Rastro até o registro original
SELECT entidade, chave_natural, motivos, arquivo_origem, linha_origem,
       registro_original
FROM BETS.STAGING.QUA_REGISTROS_REJEITADOS
WHERE lote_data = '2026-09-10' AND ARRAY_CONTAINS('valor_nao_positivo'::VARIANT, motivos)
LIMIT 5;
```

**Esperado**: o registro como veio do CSV, com arquivo e número de linha — `SC-004`. E o invariante
de `SC-005`:

```sql
SELECT entidade, qtd_recebidos, qtd_aceitos,
       qtd_recebidos - qtd_aceitos AS rejeitados_distintos
FROM BETS.MARTS.AGG_QUALIDADE_LOTE
WHERE lote_data = '2026-09-10'
GROUP BY 1,2,3;
```

**Esperado**: `qtd_recebidos = qtd_aceitos + rejeitados_distintos` em toda entidade. O mesmo
invariante roda como teste dbt em `dbt_test_marts`, então uma quebra aqui já teria falhado a DAG.

---

## Cenário 5 — Qualidade bloqueia de verdade (`FR-020`, Princípio V)

```bash
make run DATA=2026-09-10 TAXA_NULOS=0.90
```

Com 90% de nulos, as chaves de STAGING perdem integridade e um teste estrutural reprova.

**Esperado**: `dbt_test_staging` falha, a DAG para ali, `dbt_run_marts` **não** executa, e MARTS
continua mostrando os números do lote anterior. É o teste de `FR-020a`: nenhuma métrica parcial
visível.

Contraste deliberado, para mostrar que taxa alta por si só não bloqueia (`FR-016a`, `SC-009`):

```bash
make run DATA=2026-09-11 TAXA_VALOR_INVALIDO=0.60
```

**Esperado**: a DAG **conclui com sucesso**. 60% das apostas vão para a quarentena, os agregados são
calculados sobre os 40% válidos, e `agg_qualidade_lote` reporta a taxa de 0,60. A taxa reporta; ela
não bloqueia.

---

## Cenário 6 — Pendente que resolve depois (`FR-019a`, `FR-019b`)

```bash
make run DATA=2026-09-10
make run DATA=2026-09-11      # este lote traz apostas de 10/09 com status final
```

```sql
SELECT data_aposta, esporte, ggr, exposicao_pendente
FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE
WHERE data_aposta = '2026-09-10';
```

**Esperado**: o `ggr` de 10/09 mudou em relação ao cenário 1 e a `exposicao_pendente` daquela data
diminuiu. Contagem em `fct_apostas`:

```sql
SELECT COUNT(*), COUNT(DISTINCT aposta_id)
FROM BETS.MARTS.FCT_APOSTAS
WHERE data_aposta = '2026-09-10';
```

**Esperado**: os dois números iguais — o `merge` substituiu a versão em vez de criar linha nova.

---

## Cenário 7 — Reprodução por um terceiro (`SC-008`)

Em máquina limpa, apenas com Docker e Python instalados, seguindo só o README:

```bash
git clone <repo> && cd uxgroup-projeto-lakehouse
cp .env.example .env && $EDITOR .env
make setup && make up && make run DATA=2026-09-10
```

**Esperado**: métricas populadas sem nenhum passo fora do README. Qualquer comando que precise de
conhecimento não documentado reprova `SC-008` e é bug de documentação (Princípio X).

---

## Suíte completa

```bash
make test     # pytest + dbt test contra o último lote processado
```

**Esperado**: tudo verde. Esta é a checagem antes de qualquer commit e antes do ensaio da demo.

## Encerramento

```bash
make down     # derruba os contêineres, preserva os volumes
```

O warehouse Snowflake suspende sozinho em 60 segundos de inatividade, então não há ação manual para
parar de consumir crédito (Princípio I).
