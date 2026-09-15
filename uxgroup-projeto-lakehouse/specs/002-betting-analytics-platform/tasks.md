---

description: "Task list for 002-betting-analytics-platform"
---

# Tasks: Plataforma Analítica de Apostas Esportivas

**Input**: Design documents from `/specs/002-betting-analytics-platform/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUÍDOS e não opcionais neste projeto. O Princípio V da constituição exige testes de
dados em STAGING e MARTS bloqueando o pipeline, o Princípio IX proíbe cortar teste ao faltar tempo,
e `SC-002`/`SC-005` só são demonstráveis por teste automatizado.

**Organization**: Tarefas agrupadas por história de usuário, para que cada uma seja implementável e
testável de forma independente.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos distintos, sem dependência pendente)
- **[Story]**: História de usuário a que a tarefa pertence (US1–US4)
- Todo caminho de arquivo é explícito

## Path Conventions

Estrutura definida em [plan.md § Project Structure](./plan.md#project-structure): `generator/`,
`ingestion/`, `common/`, `snowflake_setup/`, `dbt_bets/`, `airflow/`, `tests/`, `docs/` na raiz do
repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Limpar o escopo anterior e preparar o esqueleto do projeto novo

- [X] T001 Remover o código do escopo anterior: apagar `src/ai/`, `src/anomaly/`, `src/brands/`, `src/evaluation/`, `src/ingestion/`, `evaluation_set/`, `infra/terraform/`, `dbt/` (inclui os seeds `brands.csv`, `category_terms.csv`, `exclusion_contexts.csv`), `tests/offline/`, `tests/fixtures/`, `scripts/checks/` e `scripts/verify/`
- [X] T002 Migrar `src/common/logging.py` para `common/logging.py` e `src/common/config.py` para `common/config.py`, removendo toda referência a BigQuery, MongoDB e MinIO; apagar `src/` ao final
- [X] T003 Reescrever `pyproject.toml`: nome `bets-lakehouse`, `requires-python = ">=3.11,<3.13"`, dependências `faker>=25,<31` e `snowflake-connector-python>=3.12,<4`; extras `transform` (`dbt-core>=1.8,<2`, `dbt-snowflake>=1.8,<2`), `orchestration` (`apache-airflow>=2.9,<3`) e `dev` (`pytest`, `pytest-cov`, `ruff`, `sqlfluff`, `pre-commit`); manter `ruff` com `T20` ativo (proíbe `print` em código de pipeline) e `[tool.setuptools.packages.find] include = ["generator*","ingestion*","common*"]`
- [X] T004 [P] Criar o esqueleto de diretórios com `__init__.py` onde aplicável: `generator/`, `ingestion/`, `common/`, `snowflake_setup/`, `dbt_bets/models/staging/`, `dbt_bets/models/marts/`, `dbt_bets/tests/`, `airflow/dags/`, `tests/unit/`, `tests/integration/`, `docs/`
- [X] T005 [P] Reescrever `.env.example` com as chaves exigidas pelo contrato e nenhum valor: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA_RAW`, `BETS_DATA_DIR`, `AIRFLOW_UID`
- [X] T006 [P] Atualizar `.gitignore` incluindo `.env`, `dados/`, `dbt_bets/target/`, `dbt_bets/logs/`, `dbt_bets/dbt_packages/`; confirmar com `git check-ignore .env` retornando `.env`
- [X] T007 [P] Atualizar `.pre-commit-config.yaml`: `ruff` sobre `generator/ ingestion/ common/ tests/`, `sqlfluff` com dialeto `snowflake` sobre `dbt_bets/models/` e `snowflake_setup/`, e varredura de segredos bloqueando commit

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: O trilho por onde qualquer história trafega — warehouse, gerador de dados válidos,
carga em RAW, projeto dbt, orquestração

**⚠️ CRITICAL**: Nenhuma história de usuário pode começar antes desta fase fechar

### Snowflake e infraestrutura local

- [X] T008 Criar `snowflake_setup/01_warehouse.sql`: `CREATE WAREHOUSE IF NOT EXISTS WH_BETS WITH WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE` — os três parâmetros são a evidência do Princípio I e não podem ser omitidos
- [X] T009 [P] Criar `snowflake_setup/02_database.sql`: `CREATE DATABASE IF NOT EXISTS BETS` e os schemas `RAW`, `STAGING`, `MARTS`
- [X] T010 [P] Criar `snowflake_setup/03_stage.sql`: file format `FF_CSV_BETS` com `TYPE = CSV`, `SKIP_HEADER = 1`, `FIELD_DELIMITER = ','`, `FIELD_OPTIONALLY_ENCLOSED_BY = '"'`, `EMPTY_FIELD_AS_NULL = TRUE`, `ENCODING = 'UTF8'`, e stage interno `RAW.STG_LOTES`
- [X] T011 Criar `snowflake_setup/04_raw_tables.sql` com `raw_apostadores`, `raw_eventos` e `raw_apostas`: **todas as colunas de negócio como `VARCHAR`, sem exceção** (RAW não tipa nem converte, `FR-004`), mais as colunas de metadados `arquivo_origem VARCHAR`, `linha_origem NUMBER`, `carregado_em TIMESTAMP_NTZ` e `lote_data DATE`; colunas na ordem exata dos arquivos em [contracts/csv-batch.md](./contracts/csv-batch.md)
- [X] T012 Criar `Makefile` com os alvos `setup` (aplica os quatro SQL em ordem via `snowflake-connector-python`, idempotente), `up`, `down`, `run DATA=<YYYY-MM-DD>`, `test` e `clean`
- [X] T013 Criar `airflow/Dockerfile` a partir de `apache/airflow:2.9.3-python3.11`, instalando dbt-core e dbt-snowflake num virtualenv isolado em `/opt/dbt-venv` — nunca no interpretador do Airflow, pelo conflito de restrições documentado em [research.md § D4](./research.md)
- [X] T014 Reescrever `docker-compose.yml` removendo os serviços `mongodb`, `minio` e `minio-init` e os volumes `mongo-data` e `minio-data`; manter `postgres`, `airflow-init`, `airflow-webserver` e `airflow-scheduler`, usando a imagem de T013, `env_file: .env` e o volume de dados `${BETS_DATA_DIR}:/opt/dados/lotes`

### Fundação Python

- [X] T015 Implementar `common/logging.py`: logger estruturado em JSON numa linha por evento, com os campos obrigatórios `lote_data`, `linhas_lidas`, `linhas_escritas`, `duracao_s` e `resultado_testes`, conforme as Restrições Técnicas Adicionais da constituição
- [X] T016 [P] Implementar `common/config.py`: leitura das variáveis de ambiente com falha imediata e mensagem nomeando a variável ausente, sem nenhum valor default para credencial (Princípio VIII)

### Gerador — dados válidos

- [X] T017 Implementar `generator/config.py` com o perfil do lote: volumes por entidade derivados de `--volume`, semente padrão `42` e as quatro taxas de defeito com os padrões do contrato (`0.05`, `0.03`, `0.02`, `0.02`)
- [X] T018 Implementar `generator/entidades.py` gerando **apenas registros válidos** de apostadores, eventos e apostas conforme os tipos de [data-model.md](./data-model.md): `estado` como sigla de UF de conjunto fechado, `esporte` de conjunto fechado, `time_casa <> time_visitante`, `data_aposta <= data_evento`, `valor_apostado > 0`, `odd >= 1`, `status` em (`ganha`, `perdida`, `pendente`, `cancelada`) e `premio_pago = 0` obrigatoriamente quando o status não é `ganha`
- [X] T019 Implementar `generator/escrita.py` com escrita CSV determinística: UTF-8 sem BOM, terminador `\n` explícito (nunca `\r\n`), cabeçalho obrigatório, decimais com duas casas e ponto, datas `YYYY-MM-DD`, timestamps `YYYY-MM-DD HH:MM:SS` em UTC, nulo como campo vazio, linhas ordenadas pela chave natural e ordem de colunas fixa; expor o SHA-256 de cada arquivo
- [X] T020 Implementar `generator/cli.py` com os argumentos e o JSON de saída de [contracts/cli.md](./contracts/cli.md), propagando a semente única para `Faker.seed()` e `random.seed()`, e validando que cada taxa está em `[0, 1]` e que a soma não passa de `1.0`
- [X] T021 [P] Escrever `tests/unit/test_determinismo.py`: gerar o mesmo lote duas vezes com a mesma semente em diretórios distintos e exigir SHA-256 idêntico arquivo por arquivo (`SC-002`, Princípio VI)
- [X] T022 [P] Escrever `tests/unit/test_data_logica.py`: garantir que nenhum módulo de `generator/` ou `ingestion/` chama `datetime.now()`, `date.today()` ou equivalente fora de campo de auditoria (`FR-003`, Princípio IV)

### Ingestão — camada RAW

- [X] T023 Implementar `ingestion/snowflake_client.py`: conexão a partir das variáveis de ambiente, `PUT file://... @STG_LOTES/<lote_data>/ OVERWRITE = TRUE` e `COPY INTO` com `FILE_FORMAT = FF_CSV_BETS`, `FORCE = TRUE` e `ON_ERROR = ABORT_STATEMENT`, capturando `METADATA$FILENAME` e `METADATA$FILE_ROW_NUMBER`
- [X] T024 Implementar `ingestion/carga_raw.py` com a substituição por lote da decisão [D1](./research.md#d1): por tabela e numa única transação, `DELETE FROM raw_<entidade> WHERE lote_data = :data_lote` e então `PUT` + `COPY INTO`; a lista de entidades é orientada por dados, para que acrescentar uma entidade não exija mudar o fluxo
- [X] T025 Implementar `ingestion/cli.py` com os argumentos `--data-lote` e `--diretorio` e o JSON de saída de [contracts/cli.md](./contracts/cli.md); nenhum segredo aceito por argumento de linha de comando
- [X] T026 Escrever `tests/integration/test_carga_raw_idempotente.py`: carregar o mesmo lote duas vezes e exigir contagem idêntica em cada tabela RAW; depois **regerar o lote com volume diferente e recarregar a mesma data**, exigindo que RAW reflita apenas o último lote — é o caso que o histórico de carga do `COPY INTO` não cobre e a razão de existir de D1

### Projeto dbt e STAGING mínima

- [X] T027 Criar `dbt_bets/dbt_project.yml`: nome `bets`, materialização padrão `view` em `staging` e `table` em `marts`, e `vars: {lote_data: ''}` para receber a data lógica do Airflow
- [X] T028 [P] Criar `dbt_bets/profiles.yml` lendo tudo de `env_var()` — `account`, `user`, `password`, `role`, `warehouse`, `database`, `schema`; nenhum valor literal (Princípio VIII)
- [X] T029 Criar `dbt_bets/models/staging/sources.yml` declarando as tabelas de `BETS.RAW` como fontes, com descrição registrando que todas as colunas são `VARCHAR` por desenho
- [X] T030 Implementar `dbt_bets/models/staging/stg_apostadores.sql`: tipagem para `apostador_id VARCHAR`, `criado_em DATE`, `estado VARCHAR(2)`, `atualizado_em TIMESTAMP_NTZ`, `lote_data DATE`
- [X] T031 [P] Implementar `dbt_bets/models/staging/stg_eventos.sql` com a tipagem da tabela de `stg_eventos` em [data-model.md](./data-model.md)
- [X] T032 Implementar `dbt_bets/models/staging/stg_apostas.sql` com a tipagem de `stg_apostas`: `valor_apostado NUMBER(12,2)`, `odd NUMBER(8,2)`, `premio_pago NUMBER(12,2)`, `data_aposta DATE`, `status VARCHAR`
- [X] T033 Criar `dbt_bets/models/staging/schema.yml` com testes `unique` e `not_null` nas chaves `apostador_id`, `evento_id` e `aposta_id`, e `accepted_values` em `status` com exatamente `['ganha','perdida','pendente','cancelada']`

### Orquestração

- [X] T034 Implementar `airflow/dags/pipeline_bets.py`: DAG `pipeline_bets`, diária, `catchup=False`, seis tarefas em cadeia — `gerar_lote → carregar_raw → dbt_run_staging → dbt_test_staging → dbt_run_marts → dbt_test_marts` — todas em `BashOperator`, com a data lógica vindo de `{{ ds }}` e descendo como `--data-lote` para as CLIs e como `--vars '{lote_data: {{ ds }}}'` para o dbt; dbt invocado por `/opt/dbt-venv/bin/dbt` com `build --fail-fast` (decisão [D3](./research.md#d3))
- [X] T035 [P] Escrever o ADR `docs/adr/0006-substituicao-de-lote-em-raw.md` justificando o `DELETE` por lote em RAW frente ao "append-only" do Princípio III — a Governance da constituição exige ADR para esta tensão, registrada em [plan.md § Complexity Tracking](./plan.md#complexity-tracking)
- [X] T036 [P] Escrever o ADR `docs/adr/0007-bashoperator-em-vez-de-cosmos.md`, que supersede o ADR 0003, com o motivo do virtualenv isolado de [research.md § D4](./research.md)

**Checkpoint**: `make setup && make up && make run DATA=<data>` gera, carrega e tipa um lote sem erro. Nenhuma métrica ainda.

---

## Phase 3: User Story 1 - GGR diário por esporte (Priority: P1) 🎯 MVP

**Goal**: O analista consulta uma tabela e vê, por dia e por esporte, total apostado, prêmios
pagos, GGR e exposição pendente.

**Independent Test**: rodar um lote e conferir que, para cada par (dia, esporte),
`ggr = total_apostado - premios_pagos` calculado à parte sobre as apostas resolvidas do lote, e que
apostas canceladas e pendentes não entraram nessas três colunas.

### Tests for User Story 1

> Escrever antes da implementação e confirmar que falham

- [X] T037 [P] [US1] Escrever `dbt_bets/tests/assert_ggr_igual_apostado_menos_premios.sql`: teste singular que falha se existir qualquer linha de `agg_ggr_diario_esporte` em que `ggr <> total_apostado - premios_pagos`
- [X] T038 [P] [US1] Escrever `dbt_bets/tests/assert_ggr_ignora_cancelada_e_pendente.sql`: falha se a soma de `total_apostado` divergir da soma de `valor_apostado` em `fct_apostas` restrita a `status IN ('ganha','perdida')` (`FR-013`)
- [X] T039 [P] [US1] Escrever `dbt_bets/tests/assert_exposicao_pendente_so_pendentes.sql`: falha se `exposicao_pendente` divergir da soma de `valor_apostado` onde `status = 'pendente'` (`FR-013a`)
- [X] T040 [P] [US1] Escrever `tests/integration/test_idempotencia_pipeline.py`: capturar contagens e somas de RAW, STAGING e MARTS, rodar o mesmo lote de novo e exigir variação zero em todos os campos (`SC-002`)
- [X] T041 [P] [US1] Escrever `tests/integration/test_pendente_resolvida.py`: processar um lote com pendentes, processar um lote posterior que traz as mesmas apostas com status final, e exigir que (a) o `ggr` da data original mudou, (b) `exposicao_pendente` daquela data caiu, e (c) `COUNT(*) = COUNT(DISTINCT aposta_id)` em `fct_apostas` (`FR-019a`, `FR-019b`)

### Implementation for User Story 1

- [X] T042 [P] [US1] Implementar `dbt_bets/models/marts/dim_eventos.sql` como tabela full-refresh com `evento_id` (chave), `esporte`, `campeonato`, `time_casa`, `time_visitante` e `data_evento`
- [X] T043 [US1] Implementar `dbt_bets/models/marts/fct_apostas.sql` incremental com `unique_key = 'aposta_id'` e `incremental_strategy = 'merge'`, desnormalizando `esporte` de `dim_eventos` e derivando `resultado_casa = valor_apostado - premio_pago`, **nulo quando a aposta não está resolvida**; o merge é o que implementa `FR-019a` (depende de T042)
- [X] T044 [US1] Implementar `dbt_bets/models/marts/agg_ggr_diario_esporte.sql` como tabela full-refresh no grão `data_aposta` × `esporte`, com `total_apostado` e `premios_pagos` restritos a `status IN ('ganha','perdida')`, `ggr` como a diferença dos dois (pode ser negativo, sem truncar em zero), `exposicao_pendente` somando `valor_apostado` de `status = 'pendente'` e `qtd_apostas_resolvidas`; full-refresh é o que faz `FR-019b` funcionar sem backfill (decisão [D2](./research.md)) (depende de T043)
- [X] T045 [US1] Criar `dbt_bets/models/marts/schema.yml` com `unique` na chave composta `(data_aposta, esporte)` e `not_null` nas duas colunas, `unique`/`not_null` em `aposta_id` de `fct_apostas`, `relationships` de `fct_apostas.evento_id` para `dim_eventos.evento_id`, e as descrições de inclusão e exclusão copiadas de [contracts/marts.md](./contracts/marts.md) (`FR-017`)
- [X] T046 [US1] Declarar `test-paths: ["tests"]` em `dbt_bets/dbt_project.yml` para que os três testes singulares de T037–T039 entrem no grafo, e confirmar que `dbt build --fail-fast` interrompe antes de `agg_*` quando um teste de `fct_apostas` reprova (`FR-020`, `FR-020a`)

**Checkpoint**: US1 entregue. `make run DATA=<data>` produz um número de GGR por esporte, e reprocessar não muda nada. É o MVP demonstrável.

---

## Phase 4: User Story 2 - Rastreabilidade da qualidade por lote (Priority: P2)

**Goal**: O engenheiro de dados vê recebidos, aceitos e rejeitados por lote, quebrados por motivo,
e abre o registro rejeitado original.

**Independent Test**: gerar um lote com proporções conhecidas de cada defeito e conferir que as
contagens por motivo em `agg_qualidade_lote` batem com o injetado, e que cada registro rejeitado é
consultável com lote e motivo.

### Tests for User Story 2

- [X] T047 [P] [US2] Escrever `tests/unit/test_defeitos.py`: para cada uma das quatro taxas, exigir que a contagem efetiva de registros defeituosos no CSV corresponda à taxa pedida com tolerância de uma linha
- [X] T048 [P] [US2] Escrever `dbt_bets/tests/assert_recebidos_igual_aceitos_mais_rejeitados.sql`: por `lote_data` e `entidade`, falha se `qtd_recebidos <> qtd_aceitos + contagem distinta de rejeitados` — comparar contagem **distinta**, porque um registro com vários motivos aparece em várias linhas de motivo e deve contar uma vez (`SC-005`)
- [X] T049 [P] [US2] Escrever `dbt_bets/tests/assert_nenhum_invalido_em_fatos.sql`: falha se `fct_apostas` contiver qualquer linha com `valor_apostado <= 0`, `premio_pago < 0`, `data_aposta > data_evento`, chave nula, `status` fora do conjunto fechado, ou `premio_pago <> 0` em status diferente de `ganha` (`FR-011`, `SC-003`)
- [X] T050 [P] [US2] Escrever `tests/integration/test_quarentena_rastreavel.py`: para uma amostra de registros rejeitados, exigir `registro_original` preenchido, `arquivo_origem` e `linha_origem` apontando para a linha correta do CSV, e `motivos` não vazio (`SC-004`)
- [X] T051 [P] [US2] Escrever `tests/integration/test_taxa_alta_nao_bloqueia.py`: rodar um lote com `--taxa-valor-invalido 0.60` e exigir que a execução **conclua com sucesso**, que os agregados sejam calculados sobre os registros válidos e que `agg_qualidade_lote` reporte a taxa (`FR-016a`, `SC-009`)

### Implementation for User Story 2

- [X] T052 [US2] Implementar `generator/defeitos.py` injetando os quatro defeitos em proporções configuráveis: duplicata divergente do mesmo `aposta_id` com `atualizado_em` diferente, nulo em campo obrigatório, `valor_apostado` zero ou negativo (contados em separado no campo `detalhe`), e `data_aposta > data_evento`; a injeção respeita a semente, para que o lote sujo continue reproduzível
- [X] T053 [US2] Ligar `generator/defeitos.py` ao `generator/cli.py` e emitir no JSON de saída a contagem efetiva por defeito, para conferência contra `agg_qualidade_lote`
- [X] T054 [US2] Reescrever `dbt_bets/models/staging/stg_apostas.sql` acrescentando a validação completa e a deduplicação: `ROW_NUMBER()` particionado por `aposta_id`, ordenado por `atualizado_em DESC` e, **como desempate, pelas demais colunas em ordem fixa** para que o resultado nunca dependa da ordem de leitura (`FR-005`, decisão [D6](./research.md)); só a linha vencedora e válida permanece
- [X] T055 [US2] Aplicar a mesma validação e deduplicação a `dbt_bets/models/staging/stg_apostadores.sql` e `dbt_bets/models/staging/stg_eventos.sql`
- [X] T056 [P] [US2] Implementar `dbt_bets/models/staging/stg_apostas_rejeitadas.sql` com o esquema de quarentena de [data-model.md](./data-model.md): `entidade`, `chave_natural` (nulo quando o próprio id veio nulo), `registro_original VARIANT` com o registro de RAW inteiro, `motivos ARRAY` com **todos** os motivos aplicáveis, `arquivo_origem`, `linha_origem`, `lote_data`, `rejeitado_em`; um registro que viola várias regras aparece uma vez só, com vários itens em `motivos`
- [X] T057 [P] [US2] Implementar `dbt_bets/models/staging/stg_apostadores_rejeitadas.sql` e `dbt_bets/models/staging/stg_eventos_rejeitadas.sql` com o mesmo esquema
- [X] T058 [US2] Implementar `dbt_bets/models/staging/qua_registros_rejeitados.sql` como view de `UNION ALL` dos modelos de quarentena, única fonte do agregado de qualidade (depende de T056, T057)
- [X] T059 [US2] Implementar `dbt_bets/models/marts/agg_qualidade_lote.sql` como tabela full-refresh no grão `lote_data` × `entidade` × `motivo`, com `qtd_recebidos` (linhas de RAW da entidade no lote), `qtd_aceitos`, `qtd_rejeitados` e `taxa_rejeicao NUMBER(5,4)` (depende de T058)
- [X] T060 [US2] Acrescentar a `dbt_bets/models/staging/schema.yml` o teste `accepted_values` sobre os motivos desaninhados, com exatamente o catálogo fechado de [data-model.md](./data-model.md): `duplicata`, `nulo_obrigatorio`, `valor_nao_positivo`, `data_posterior_ao_evento`, `apostador_inexistente`, `evento_inexistente`, `premio_inconsistente`, `status_invalido`
- [X] T061 [US2] Acrescentar a `dbt_bets/models/marts/schema.yml` `unique` na chave composta `(lote_data, entidade, motivo)`, `not_null` nas três colunas, e a descrição de `agg_qualidade_lote` registrando que a taxa reporta e não bloqueia

**Checkpoint**: US1 e US2 funcionam independentemente. A demo já tem seu momento mais forte: sujeira entra, quarentena registra, métricas ficam limpas.

---

## Phase 5: User Story 3 - Engajamento diário dos apostadores (Priority: P3)

**Goal**: O analista vê volume apostado, ticket médio e apostadores ativos por dia.

**Independent Test**: processar um lote e conferir que volume, ticket médio e ativos correspondem à
soma, à média e à contagem distinta calculadas à parte sobre as apostas válidas do dia.

### Tests for User Story 3

- [X] T062 [P] [US3] Escrever `dbt_bets/tests/assert_ticket_medio_nulo_sem_apostas.sql`: falha se `ticket_medio` for zero em vez de **nulo** numa data com `qtd_apostas = 0`, e falha em qualquer divisão por zero
- [X] T063 [P] [US3] Escrever `dbt_bets/tests/assert_apostadores_ativos_distintos.sql`: falha se `apostadores_ativos` divergir da contagem distinta de `apostador_id` com ao menos uma aposta válida na data — um apostador com várias apostas no dia conta uma vez
- [X] T064 [P] [US3] Escrever `dbt_bets/tests/assert_volume_engajamento_inclui_todos_status.sql`: falha se `volume_apostado` divergir da soma de `valor_apostado` de **todas** as apostas válidas, inclusive `pendente` e `cancelada` — critério deliberadamente diferente do GGR (`FR-014` vs `FR-013`)

### Implementation for User Story 3

- [X] T065 [P] [US3] Implementar `dbt_bets/models/marts/dim_apostadores.sql` como tabela full-refresh com `apostador_id` (chave), `criado_em`, `estado` e `antiguidade_dias`
- [X] T066 [US3] Implementar `dbt_bets/models/marts/agg_engajamento_diario.sql` como tabela full-refresh no grão `data_aposta`, com `volume_apostado` sobre todas as apostas válidas, `ticket_medio` **nulo e não zero** quando `qtd_apostas = 0`, `apostadores_ativos` como contagem distinta e `qtd_apostas`; datas sem aposta válida aparecem com volume zero e ativos zero, nunca ausentes
- [X] T067 [US3] Acrescentar a `dbt_bets/models/marts/schema.yml` `unique` e `not_null` em `data_aposta`, `relationships` de `fct_apostas.apostador_id` para `dim_apostadores.apostador_id`, e a advertência de [contracts/marts.md](./contracts/marts.md) de que `volume_apostado` não é comparável a `total_apostado` do GGR

**Checkpoint**: US1, US2 e US3 independentes e verdes.

---

## Phase 6: User Story 4 - Movimentação financeira diária (Priority: P4)

**Goal**: O time financeiro compara depósitos e saques por dia e vê o líquido.

**Independent Test**: processar um lote com depósitos e saques conhecidos e conferir que os totais
diários e o líquido correspondem à soma independente por tipo.

### Tests for User Story 4

- [X] T068 [P] [US4] Escrever `dbt_bets/tests/assert_liquido_igual_depositos_menos_saques.sql`: falha se `liquido <> total_depositado - total_sacado` em qualquer linha, incluindo as de líquido negativo
- [X] T069 [P] [US4] Escrever `tests/integration/test_financeiro_liquido_negativo.py`: gerar um lote em que os saques superam os depósitos e exigir que `liquido` saia negativo, sem erro e sem truncar em zero

### Implementation for User Story 4

- [X] T070 [US4] Estender `generator/entidades.py` com a geração de transações válidas: `transacao_id`, `apostador_id` existente, `data_transacao`, `tipo` em (`deposito`, `saque`) e `valor > 0`; acrescentar `transacoes_<data>.csv` a `generator/escrita.py` na ordem de colunas de [contracts/csv-batch.md](./contracts/csv-batch.md)
- [X] T071 [US4] Acrescentar `raw_transacoes` a `snowflake_setup/04_raw_tables.sql`, todas as colunas de negócio `VARCHAR`, com as mesmas quatro colunas de metadados
- [X] T072 [US4] Registrar `raw_transacoes` na lista orientada a dados de `ingestion/carga_raw.py` — se T024 ficou bem feita, esta tarefa é uma linha de configuração e nenhuma mudança de fluxo
- [X] T073 [P] [US4] Implementar `dbt_bets/models/staging/stg_transacoes.sql` com tipagem `valor NUMBER(12,2)`, `data_transacao DATE`, `tipo` de conjunto fechado, mais deduplicação por `atualizado_em` e validação (`valor > 0`, `tipo` válido, FK de apostador), e `dbt_bets/models/staging/stg_transacoes_rejeitadas.sql` com o esquema de quarentena
- [X] T074 [US4] Acrescentar `stg_transacoes_rejeitadas` ao `UNION ALL` de `dbt_bets/models/staging/qua_registros_rejeitados.sql`, para que a entidade entre no agregado de qualidade (depende de T073)
- [X] T075 [P] [US4] Implementar `dbt_bets/models/marts/fct_transacoes.sql` incremental com `unique_key = 'transacao_id'` e estratégia `merge`
- [X] T076 [US4] Implementar `dbt_bets/models/marts/agg_financeiro_diario.sql` como tabela full-refresh no grão `data_transacao`, com `total_depositado`, `total_sacado`, `liquido` (pode ser negativo), `qtd_depositos` e `qtd_saques` (depende de T075)
- [X] T077 [US4] Acrescentar a `dbt_bets/models/marts/schema.yml` `unique`/`not_null` em `data_transacao`, `accepted_values` em `tipo` com `['deposito','saque']`, e a descrição registrando que este mart não se reconcilia com o GGR

**Checkpoint**: as quatro histórias entregues e independentemente testáveis.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T078 Escrever o `README.md` da raiz com diagrama da arquitetura medallion (RAW → STAGING → MARTS), pré-requisitos com versões, configuração de credenciais via `.env`, passo a passo de execução e **declaração explícita de que os dados são sintéticos**; todo comando citado deve funcionar exatamente como escrito (Princípio X, `FR-017`, `FR-006` da spec de dados sintéticos)
- [X] T079 [P] Escrever `docs/arquitetura.md` com o diagrama e a linhagem gerada a partir do grafo do dbt, não desenhada à mão
- [X] T080 [P] Escrever `docs/metricas.md` como dicionário de métricas, com os blocos "inclui" e "não inclui" de [contracts/marts.md](./contracts/marts.md) para as quatro tabelas, incluindo a ressalva de que o GGR de um dia passado pode mudar quando uma pendente resolve
- [X] T081 [P] Reescrever `docs/demo_script.md` para o escopo atual, ancorado nos cenários 1, 4 e 5 de [quickstart.md](./quickstart.md), cabendo em 10 minutos (`SC-007`)
- [X] T082 [P] Escrever `docs/adr/0008-supersedidos-pelo-escopo-bets.md` marcando os ADRs 0001, 0002, 0004 e 0005 como superados pela mudança de escopo da constituição v2.0.0
- [X] T083 [P] Arquivar `specs/001-brand-mention-intelligence/` marcando-a como superada, para que ninguém a confunda com a especificação vigente
- [ ] T084 Rodar todos os sete cenários de [quickstart.md](./quickstart.md) numa máquina limpa e corrigir qualquer passo que não funcione como documentado (`SC-008`)
  - Progresso (2026-09-13): máquina não tinha Python, `make`, Docker Desktop rodando nem WSL2 configurado — instalados/ativados nesta sessão (winget + grupo `docker-users`, exigiu reiniciar). `make up` sobe Postgres + Airflow com sucesso.
  - **Cenário 1** (lote novo pela DAG): validado — `make run DATA=<data>` roda as 6 tarefas verdes via Airflow real (não só `run-local`).
  - **Cenário 2** (reprocessar não altera nada): validado via Airflow real — `2026-09-10` rodado duas vezes seguidas pela DAG (não só `test-integracao`/`run-local`); RAW, STAGING, quarentena e todos os agregados de MARTS idênticos campo a campo entre as duas execuções, variação zero (SC-002). Corrigido o nome do teste no doc (era `test_idempotencia.py`, o arquivo real é `test_idempotencia_pipeline.py`).
  - **Cenário 3** (determinismo do gerador): coberto por `make test` (teste unitário).
  - **Cenário 4** (rastreabilidade de qualidade): coberto pelas execuções reais acima — `agg_qualidade_lote` e `qua_registros_rejeitados` populados e corretos.
  - **Cenário 5** (portão de qualidade): **rodado de verdade e a narrativa do doc estava errada** — `TAXA_NULOS=0.90` NÃO derruba nenhum teste (a quarentena filtra antes, exatamente como `FR-016a` manda); a DAG termina com sucesso. `docs/demo_script.md` corrigido para refletir o comportamento real em vez de uma alegação que nunca se sustentaria ao vivo.
  - **Cenário 6** (pendente resolvida): **bug real encontrado e corrigido** — a DAG nunca passava `--resolver-pendentes-de` para o gerador; a resolução automática documentada no `demo_script.md` simplesmente não acontecia. Corrigida a tarefa `gerar_lote` em `pipeline_bets.py` para detectar o lote do dia anterior em disco e resolver pendências automaticamente, sem quebrar a primeira execução de uma data nova (que não tem o que resolver). Validado ao vivo: GGR de `2026-09-10` mudou e exposição pendente caiu depois de rodar `2026-09-11`.
  - **Cenário 7** (reprodução por terceiro): não testado via clone separado, mas esta sessão partiu de um estado equivalente (sem Python, sem make, sem Docker rodando) e chegou a métricas populadas seguindo o README/Makefile.
  - Defeitos adicionais encontrados e corrigidos no caminho da DAG real: `airflow dags trigger --logical-date` não existe nesta versão (é `-e`/`--exec-date`); o alvo `run` do Makefile nunca repassava `TAXA_NULOS`/`TAXA_VALOR_INVALIDO`/`VOLUME` como `--conf` para a DAG, então essas variáveis do quickstart eram silenciosamente ignoradas.
  - **Achado que não é bug**: acionar `make run` com uma data futura (depois de hoje) deixa o dag run preso em `queued` para sempre — é comportamento do Airflow com `catchup=False`, não um defeito do projeto. Usar sempre uma data igual ou anterior a hoje.
- [X] T085 Rodar o alvo `test` do `Makefile` e todos os hooks de `.pre-commit-config.yaml`, exigindo `ruff`, `sqlfluff`, pytest e `dbt test` verdes, e nenhuma credencial no diff nem no histórico (Princípio VIII)
  - Concluído em 2026-09-13. `make test` (pytest + ruff) verde. `make test-integracao` verde **23/23** contra o Snowflake real (primeira vez rodando o pipeline inteiro contra a conta trial de verdade). `dbt build --fail-fast` verde 99/99. `ruff check`, `ruff format --check` e `sqlfluff lint` (rodados diretamente, ver nota abaixo) limpos em todo o código. Varredura de credencial no diff limpa.
  - **Nota sobre o pre-commit**: o repositório inteiro está versionado dentro de uma subpasta `uxgroup-projeto-lakehouse/` aninhada — a raiz do Git não é a raiz do projeto (só um `README.md` solto na raiz de verdade). Os padrões de arquivo do `.pre-commit-config.yaml` (`files: ^(generator|ingestion|...)/`) assumem raiz do Git = raiz do projeto e por isso não encontram nada para checar quando o hook roda de verdade. Isso já vem do histórico (commits anteriores), não é desta sessão. Contornado rodando `ruff`/`ruff format`/`sqlfluff` diretamente nos caminhos certos — a cobertura é a mesma, só não passa pelo `pre-commit run`. Vale decidir depois se acha o repositório de volta pra raiz do Git ou ajusta os padrões do `.pre-commit-config.yaml` para a subpasta.
  - Defeitos reais encontrados e corrigidos ao rodar contra Snowflake pela primeira vez (nenhum detectável por parse):
    1. `fct_apostas`/`fct_transacoes` usavam `merge` incremental puro, que nunca apaga linha — ao reprocessar a mesma `lote_data` com conteúdo diferente (ex.: outro volume), `aposta_id`/`transacao_id` da geração anterior ficavam órfãos das dimensões full-refresh, violando o edge case "Reprocessamento com conteúdo diferente" da spec. Corrigido com um `pre_hook` (`dbt_bets/macros/apagar_orfaos_do_lote.sql`) que estende a substituição por lote da decisão D1 (RAW) até a camada de fato. **Vale registrar um ADR para esta decisão** (Princípio IX exige justificativa escrita para complexidade nova) — não feito ainda.
    2. Os 5 arquivos de `tests/integration/` reutilizavam as mesmas datas (`2026-09-10` e vizinhas) como `lote_data`, causando contaminação cruzada entre arquivos ao rodar na mesma sessão contra um warehouse compartilhado. Datas isoladas por arquivo em `2026-02-01`–`2026-02-08`.
    3. Em `test_pendente_resolvida.py`, a fixture `dois_lotes` era de escopo `function` (repetia a cada teste do arquivo) e não limpava o estado anterior de DIA_1/DIA_2 no Snowflake — cada nova chamada herdava a resolução da anterior, zerando a diferença que os testes mediam. Corrigido com escopo `module` e limpeza explícita de RAW **e** dos fatos no início da fixture.
    4. `enviar_para_stage`/`copiar_para_raw` (`ingestion/snowflake_client.py`) não verificavam que o arquivo enviado por `PUT` já estava visível no stage antes do `COPY INTO` — risco raro mas real de carregar silenciosamente zero linhas. Adicionada checagem via `LIST` com retentativa antes do `COPY INTO`, falhando alto em vez de silencioso se persistir.
  - Dívida de estilo pré-existente (13 arquivos Python sem `ruff format`, ~220 avisos de `sqlfluff`, nenhum em arquivo tocado nesta sessão) foi corrigida a pedido do usuário: `ruff format` aplicado a todo o código, `sqlfluff fix` aplicado às SQL, mais 6 correções manuais (aliases faltando, palavra reservada `volume` como identificador).
- [ ] T086 Ensaiar a apresentação seguindo `docs/demo_script.md` ao menos uma vez de ponta a ponta, com cronômetro, e ajustar o roteiro no próprio arquivo conforme o tempo medido — o Princípio IX proíbe começar qualquer refinamento antes disto
- [X] T087 OPCIONAL, somente após T086 estar concluída: dashboard de visualização em `dashboard/` sobre as tabelas de MARTS, com a ferramenta a definir no momento. Está fora do escopo obrigatório e nenhum critério de sucesso depende dele
  - Concluído em 2026-09-13, a pedido explícito do usuário antes de T086 estar formalmente marcada — desvio consciente da ordem sugerida pelo Princípio IX, não um esquecimento.
  - Ferramenta: **Streamlit** (`dashboard/app.py`), somente leitura sobre `BETS.MARTS`. Reaproveita `common/config.py` para credenciais — nenhum segredo novo. Extra `dashboard` em `pyproject.toml` (streamlit, pandas, altair); alvo `make dashboard`.
  - Validado sem navegador: `streamlit.testing.v1.AppTest` rodou o script inteiro contra o Snowflake real, zero exceções, 4 métricas e 4 abas renderizando com dados de verdade (GGR, engajamento, financeiro, qualidade do lote).
  - Declaração de dados sintéticos incluída na própria tela, conforme Princípio VI exige de qualquer apresentação dos dados.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende da Phase 1 — **bloqueia todas as histórias**
- **US1 (Phase 3)**: depende da Phase 2
- **US2 (Phase 4)**: depende da Phase 2. Modifica os modelos de STAGING criados em T030–T032, então **não** roda em paralelo com tarefas que tocam os mesmos arquivos
- **US3 (Phase 5)**: depende da Phase 2 e de `fct_apostas` (T043)
- **US4 (Phase 6)**: depende da Phase 2; é a história mais isolada, com entidade e mart próprios
- **Polish (Phase 7)**: depende das histórias desejadas estarem prontas

### User Story Dependencies

- **US1 (P1)**: independente. Entrega valor sozinha e é o MVP
- **US2 (P2)**: independente no resultado, mas reescreve os modelos de STAGING da fundação — conflito de arquivo com US1 se paralelizada sem cuidado
- **US3 (P3)**: consome `fct_apostas` de US1; sem ela, precisaria de um fato próprio
- **US4 (P4)**: totalmente independente das outras três

### Parallel Opportunities

- **Phase 1**: T004, T005, T006 e T007 em paralelo depois de T001–T003
- **Phase 2**: T009 e T010 em paralelo com T008; T016 com T015; T021 e T022 entre si; T028 com T027; T031 com T030; T035 e T036 em paralelo com qualquer coisa
- **US1**: os cinco testes T037–T041 em paralelo; T042 em paralelo com eles
- **US2**: T047–T051 em paralelo; T056 e T057 em paralelo
- **US3**: T062–T064 em paralelo; T065 em paralelo com eles
- **US4**: T068 e T069 em paralelo; T073 e T075 em paralelo
- **Polish**: T079–T083 todas em paralelo

### Paralelismo entre histórias

Com uma pessoa só e 3 dias, o paralelismo real é baixo e a ordem P1 → P2 → P3 → P4 é a
recomendada. Com duas pessoas, US4 é a candidata natural à segunda frente: não toca nenhum arquivo
de US1, US2 ou US3, exceto a lista de entidades da ingestão e o `UNION ALL` da quarentena.

---

## Parallel Example: User Story 1

```bash
# Os cinco testes de US1 de uma vez:
Task: "Teste singular de identidade do GGR em dbt_bets/tests/assert_ggr_igual_apostado_menos_premios.sql"
Task: "Teste singular de exclusão de cancelada e pendente em dbt_bets/tests/assert_ggr_ignora_cancelada_e_pendente.sql"
Task: "Teste singular de exposição pendente em dbt_bets/tests/assert_exposicao_pendente_so_pendentes.sql"
Task: "Teste de idempotência do pipeline em tests/integration/test_idempotencia_pipeline.py"
Task: "Teste de pendente resolvida em lote posterior em tests/integration/test_pendente_resolvida.py"

# E a dimensão, que não depende de nenhum deles:
Task: "Implementar dim_eventos em dbt_bets/models/marts/dim_eventos.sql"
```

---

## Implementation Strategy

### MVP First (US1 apenas)

1. Phase 1 — Setup
2. Phase 2 — Foundational (crítica; bloqueia tudo)
3. Phase 3 — US1
4. **PARAR E VALIDAR**: cenários 1, 2, 3 e 6 do [quickstart.md](./quickstart.md)
5. Neste ponto já existe demo defensável

### Entrega incremental por dia

O sequenciamento de [plan.md](./plan.md#sequenciamento-3-dias) mapeia assim:

- **Dia 1**: T001–T046 — Setup, Foundational e US1. Fim do dia: um GGR sai do Snowflake por comando único
- **Dia 2**: T047–T061 — US2, a tese do projeto: sujeira entra, quarentena registra, métricas ficam limpas
- **Dia 3**: T062–T086 — US3, US4, documentação e ensaio. T087 só se sobrar tempo

### Se o tempo apertar

A ordem de corte é da cauda para a cabeça: T087 primeiro, depois US4 (T068–T077), depois US3
(T062–T067). **Nunca** cortar T078 (README), T084 (validação do quickstart), T085 (suíte verde) nem
T086 (ensaio) — o Princípio IX classifica os quatro como inegociáveis.

---

## Notes

- `[P]` significa arquivos distintos e nenhuma dependência pendente
- A etiqueta `[Story]` dá a rastreabilidade de cada tarefa até a história de usuário
- Confirmar que o teste falha antes de implementar, nas fases que têm testes primeiro
- Commit por tarefa ou por grupo lógico coerente
- Parar em qualquer checkpoint para validar a história de forma isolada
