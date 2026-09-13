---
description: "Task list for Brand Mention Intelligence implementation"
---

# Tasks: Brand Mention Intelligence — Share of Voice de Marcas de Apostas

**Input**: Design documents from `/specs/001-brand-mention-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: **OBRIGATÓRIOS**. Não são opcionais neste projeto — SC-007 a SC-010 e SC-016 os exigem
como critério de sucesso, e os Princípios I, II, III, IV e IX da constituição definem testes
específicos como condição de conformidade. Teste nunca é cortado (Princípio XIV).

**Organization**: agrupadas por história de usuário (P1–P11), para entrega incremental sob prazo
fixo de 7 dias.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: história a que pertence (US1–US11)

## Path Conventions

Raiz do repositório, conforme `plan.md`: `src/`, `dags/`, `dbt/`, `evaluation_set/`, `infra/`,
`tests/`, `docs/`.

---

## Phase 1: Verificações Bloqueantes das Fontes

**Purpose**: nada — nem estrutura de repositório — depende disto, mas **nenhum código de ingestão
ou transformação começa antes que esta fase passe inteira**. O enunciado do plano é explícito:
não presumir capacidade de endpoint nem estrutura de tabela.

**⚠️ Custo**: todas as verificações abaixo são de custo zero (metadados, dry run e ≤ 5 requisições).

- [ ] T139 **[AÇÃO MANUAL DO AUTOR — bloqueia T002–T006]** Provisionar o ambiente GCP: criar o projeto, habilitar billing, criar service account com papel mínimo (`roles/bigquery.jobUser` + `roles/bigquery.dataEditor` nos datasets do projeto), baixar a chave para fora do repositório, configurar a **cota `Query usage per day`** e o alerta de orçamento em R$ 0,01. Registrar o procedimento em `docs/gcp_setup.md`
- [ ] T001 Criar `scripts/verify/__init__.py` e o alvo `make verify-sources` em `Makefile`, que executa V1→V9 em ordem e falha na primeira reprovação
- [ ] T002 [P] V1: implementar `scripts/verify/v1_partition_freshness.py` — consultar `SELECT MAX(_PARTITIONTIME) FROM gdelt-bq.gdeltv2.gkg_partitioned` e reprovar se a última partição tiver mais de 7 dias de atraso
- [ ] T003 [P] V2: implementar `scripts/verify/v2_schema.py` — executar `bq show --schema gdelt-bq:gdeltv2.gkg_partitioned` e gravar o esquema real em `docs/gkg_schema.json`, confirmando as colunas `DATE`, `DocumentIdentifier`, `V2SourceCommonName`, `V2Themes`, `V2Tone`
- [ ] T004 V3: implementar `scripts/verify/v3_dry_run_budget.py` — dry run de **1 dia** com as 4 colunas mínimas, extrapolar × 365, comparar com o orçamento de **200 GiB** e reprovar se estourar (depende de T003)
- [ ] T005 [P] V4: implementar `scripts/verify/v4_project_quota.py` — confirmar que a cota `Query usage per day` está configurada no projeto GCP; reprovar se ausente, pois é a trava primária do Princípio I
- [ ] T006 [P] V5: implementar `scripts/verify/v5_max_bytes_billed.py` — submeter query deliberadamente grande com teto baixo e reprovar se ela **executar** em vez de falhar
- [ ] T007 [P] V6: implementar `scripts/verify/v6_doc_modes.py` — 1 requisição real por modo (`ArtList`, `TimelineVolRaw`, `TimelineTone`), salvando as respostas em `tests/fixtures/gdelt/`
- [ ] T008 [P] V7: implementar `scripts/verify/v7_artlist_volume.py` — verificar se a marca de maior volume atinge 250 artigos em um dia; se sim, sinalizar necessidade de fatiamento por subjanela
- [ ] T009 [P] V8: implementar `scripts/verify/v8_rate_limit.py` — provocar e capturar a resposta real de rate limit da DOC 2.0 em `tests/fixtures/gdelt/rate_limit_response.json`, para calibrar o backoff ao que existe e não ao suposto
- [ ] T010 [P] V9: implementar `scripts/verify/v9_spa_mf.py` — verificar se a página da SPA/MF expõe arquivo estruturado (CSV/XLSX); se não, acionar o plano B do seed transcrito
- [ ] T011 Consolidar todos os resultados em `docs/source_verification.md`, com data, comando executado e saída de cada verificação (depende de T002–T010)
- [X] T012 Registrar em `spec.md` a decisão sobre os dois conflitos identificados no plano: reescrever **FR-023** para reconciliação medida, e separar **SC-006** em SLA de ciclo diário vs. backfill

**Checkpoint**: fontes verificadas e conflitos resolvidos. Só agora se escreve código de produção.

---

## Phase 2: Setup (Infraestrutura Compartilhada)

**Purpose**: esqueleto do projeto e ambiente reproduzível de um comando.

- [X] T013 Criar a árvore de diretórios de `plan.md`: `src/{ingestion,brands,evaluation,anomaly,ai,common}`, `dags/`, `dbt/`, `evaluation_set/`, `infra/terraform/`, `tests/{unit,integration,offline,fixtures}`, `docs/adr/`
- [X] T014 [P] Criar `pyproject.toml` com Python 3.11 e dependências fixadas: `requests`, `google-cloud-bigquery`, `pymongo`, `boto3`, `pydantic`, `dbt-core`, `dbt-bigquery`, `apache-airflow`, `astronomer-cosmos`, `pytest`
- [X] T015 [P] Configurar `.pre-commit-config.yaml` com `ruff` (lint + format), `sqlfluff` (dialeto bigquery) e `dbt-checkpoint` (exige `description` em coluna de mart)
- [X] T016 [P] Criar `.env.example` documentando todas as chaves esperadas **sem valores** e `.gitignore` bloqueando `.env`, credenciais e `*.json` de service account
- [X] T017 Criar `docker-compose.yml` com Airflow, PostgreSQL (metastore + serving), MongoDB (landing) e MinIO (object storage S3-compatível)
- [X] T018 Criar `Makefile` com `up`, `down`, `status`, `test`, `backfill`, `run`, `check-idempotency`, `eval`, `docs`, `clean` e `verify-sources`
- [X] T019 [P] Inicializar projeto dbt em `dbt/` com `dbt_project.yml` e `profiles.yml` apontando para datasets separados por camada e ambiente, particionados por data e clusterizados por marca
- [X] T145 [P] Criar `dbt/packages.yml` com `dbt-utils` e `dbt-expectations` e incluir `dbt deps` no alvo `make up` — sem isto T071 não roda
- [X] T151 [P] Documentar em `dbt/README.md` o mapeamento entre as camadas da constituição (landing → bronze → silver → gold) e os diretórios do dbt (`staging/` → `intermediate/` → `marts/`), para que a regra "uma camada só lê da imediatamente anterior" seja verificável na linhagem (Princípio V)
- [X] T020 [P] Criar `infra/terraform/main.tf` declarando os datasets `bronze`, `silver` e `gold`, tabelas e permissões, aplicável do zero
- [X] T021 [P] Criar `.github/workflows/ci.yml`: em PR rodar lint Python e SQL, testes unitários, `dbt compile` e a avaliação de precisão; em merge na `main` publicar a documentação
- [X] T022 [P] Criar `docs/adr/template.md` e o índice `docs/adr/README.md`
- [X] T023 [P] Escrever os ADRs das decisões já tomadas em `research.md`: `0001-bigquery-billing-vs-sandbox.md` (sandbox descartado por bloquear DML), `0002-cliente-http-proprio.md` (`gdeltdoc` descartado), `0003-cosmos-para-dbt-no-airflow.md` (`BashOperator` descartado), `0004-duas-fontes-gdelt.md`
- [X] T024 [P] Criar `docs/demo_script.md` com o esqueleto do roteiro de 10 minutos — **existe desde o dia 1 e nunca é cortado** (Princípio XIV)

**Checkpoint**: `make up` sobe o ambiente completo em máquina limpa.

---

## Phase 3: Foundational (Pré-requisitos Bloqueantes)

**Purpose**: infraestrutura de código que TODAS as histórias exigem. As travas dos Princípios I e
II vivem aqui e são testadas aqui.

**⚠️ CRÍTICO**: nenhuma história começa antes desta fase terminar.

### Configuração e observabilidade

- [X] T025 Implementar `src/common/config.py` — configuração central com `max_bytes_billed`, `confidence_floor`, `confidence_floor_version`, `requests_per_run`, `min_request_interval_seconds` (5), `anomaly_n_mad` e `whitespace_min_threshold`. Nenhum destes valores pode ser sobrescrito por chamada
- [X] T026 Implementar `src/common/logging.py` — log estruturado com os campos obrigatórios do Princípio XI: `logical_date`, `rows_read`, `rows_written`, `bytes_estimated`, `bytes_billed`, `duration_ms`, `test_result`, `external_failure`
- [X] T027 [P] Escrever `tests/unit/test_logging.py` — reprovar se `print(` aparecer em qualquer módulo sob `src/` (Princípio XI)

### Cliente HTTP — Princípio II (NÃO-NEGOCIÁVEL)

- [X] T028 Implementar `src/ingestion/http_client.py` conforme `contracts/gdelt-doc-api.md`: User-Agent com nome do projeto e contato, backoff exponencial com jitter, teto de tentativas, timeout, limite de requisições por execução, requisições em série com intervalo mínimo de 5 s, e cache em disco por `request_hash` (SHA-256 da URL canônica)
- [X] T029 Escrever `tests/unit/test_http_client.py` cobrindo os seis invariantes do contrato: UA presente e sem `Mozilla`; duas requisições idênticas ⇒ **uma** ida à rede; intervalo mínimo de 5 s respeitado; `429`/`5xx` ⇒ backoff com jitter e parada no teto; limite por execução lido de config; falha limpa ao esgotar tentativas (depende de T028)

### Guarda do BigQuery — Princípio I (NÃO-NEGOCIÁVEL)

- [X] T030 Implementar `src/ingestion/bigquery_client.py` com a classe `BigQueryGuard` de `contracts/bigquery-gkg.md` — **ponto único de acesso** à origem pública, aplicando as quatro travas na ordem: validar filtro de partição → dry run com bytes em log → checar orçamento → executar com `maximum_bytes_billed`
- [X] T031 Escrever `tests/unit/test_bigquery_guard.py` — SQL sem `_PARTITIONTIME` levanta exceção **antes de qualquer chamada de rede**; `SELECT *` é rejeitado; `_execute` nunca é chamado sem `_dry_run` anterior; `maximum_bytes_billed` sempre presente no job config (depende de T030)
- [X] T032 Escrever `tests/unit/test_no_bigquery_bypass.py` — varrer `src/` e `dags/` e reprovar se qualquer módulo fora de `bigquery_client.py` importar o cliente BigQuery diretamente. Sem isso as travas seriam contornáveis por um caminho de código alternativo

### Zona bruta — Princípio III (NÃO-NEGOCIÁVEL)

- [X] T033 Implementar `src/ingestion/landing.py` — persistir a resposta **byte a byte, antes de qualquer parse**, na coleção `mongo.landing.gdelt_doc_responses` com todos os campos de `data-model.md`, incluindo `raw_body`, `truncated_at_max` e índice único `(request_hash, logical_date)`
- [X] T034 Implementar a escrita Parquet em `minio://landing/gkg/dt=YYYY-MM-DD/` via `boto3` com `endpoint_url` configurável, para que migrar para S3 real seja troca de variável de ambiente
- [X] T035 Escrever `tests/unit/test_landing_immutability.py` — arquivo da zona bruta nunca é sobrescrito nem editado; recaptura da mesma resposta não duplica linha
- [X] T036 Criar o harness de rede desabilitada em `tests/offline/conftest.py` — fixture que bloqueia toda saída de rede, usada pela suíte inteira
- [ ] T140 Escrever `tests/unit/test_no_personal_data.py` — varrer o esquema de todas as camadas e reprovar coluna que contenha dado pessoal (nome de pessoa, e-mail, telefone, documento, IP, identificador de usuário), conforme o critério de verificação do Princípio XII (FR-012)
- [X] T150 Antecipar a prova do Princípio III: escrever `tests/offline/test_full_reconstruction.py` já nesta fase, inicialmente cobrindo apenas as camadas existentes, e estendê-lo a cada nova camada. **Substitui T129**, que ficava tarde demais para dar tempo de correção

### Cadastro de marcas e dimensões compartilhadas

- [X] T037 Criar `dbt/seeds/brands.csv` com as 7 marcas e todos os campos de `dim_brand`: `brand_id`, `name`, `canonical_domain` (`reals.bet.br`, `betgo.bet.br`, `bingo.bet.br`, `kto.bet.br`, `esportiva.bet.br`, `brazino777.bet.br`, `superbet.bet.br`), `known_variants[]`, `role` (própria/concorrente), `ambiguity_risk` (alto para Reals/Bingo/Esportiva/BetGO/KTO, baixo para Brazino777/Superbet), `monitored_since`
- [X] T038 [P] Criar `dbt/seeds/category_terms.csv` — lista de termos do setor versionada, com `term_list_version` e data de vigência (FR-013a)
- [X] T039 [P] Criar `dbt/seeds/exclusion_contexts.csv` — contextos que geram falso positivo por marca: moeda e clubes para Reals, jogo e interjeição para Bingo, expressão "aposta esportiva" e nomes de veículos para Esportiva, siglas genéricas para BetGO e KTO
- [X] T040 [P] Implementar `src/brands/registry.py` — carga tipada do cadastro, com type hints e docstring explicando o porquê do módulo
- [ ] T041 Criar `dbt/models/marts/dim_brand.sql` (materialização `table`) a partir do seed
- [ ] T042 [P] Criar `dbt/models/marts/dim_date.sql`, `dim_language.sql` e `dim_country.sql`

### Orquestração

- [ ] T043 Criar `dags/daily_mentions.py` com o esqueleto do DAG e **data lógica explícita** passada ao dbt — nenhuma etapa usa data corrente implícita (Princípio IX)
- [ ] T044 Criar `dags/historical_backfill.py` — DAG separado, agendamento `None`, para que a extração histórica **nunca rode acidentalmente** no ciclo diário
- [ ] T045 Integrar `astronomer-cosmos` em `dags/daily_mentions.py` com `DbtTaskGroup`, de modo que cada modelo dbt apareça como tarefa própria no grafo, não como comando opaco (Princípio XI)

**Checkpoint**: travas de custo e cidadania testadas, zona bruta imutável, DAGs esqueleto no ar.

---

## Phase 4: User Story 1 — Identificação de Marca Auditável (P1) 🎯 MVP

**Goal**: identificar marcas em 4 camadas de confiança decrescente e publicar precisão e revocação
medidas contra um conjunto rotulado versionado.

**Independent Test**: rodar `make eval` e obter precisão e revocação por marca e por camada, sem
que nenhuma métrica de negócio exista ainda.

### Conjunto de avaliação — entregável de primeira classe

- [ ] T046 [US1] Escrever `evaluation_set/README.md` com a metodologia de amostragem estratificada **antes de rotular** — o critério escrito antes evita viés de confirmação
- [ ] T047 [US1] Implementar `src/evaluation/sampler.py` — amostragem estratificada por `ambiguity_case`, garantindo cobertura obrigatória de Reals, Bingo e Esportiva (SC-004)
- [ ] T048 [US1] Gerar e rotular manualmente `evaluation_set/labeled_mentions.csv` com **≥ 300 menções**, campos `candidate_id`, `article_url`, `title`, `outlet_domain`, `brand_candidate`, `human_label` (`marca`|`nao_marca`), `label_reason`, `labeled_by`, `labeled_at`, `ambiguity_case` (depende de T047)

### Camadas de identificação

- [X] T049 [P] [US1] Implementar `src/brands/layer1_domain.py` — âncora de domínio `.bet.br` no conteúdo ou na URL; confiança máxima
- [X] T050 [P] [US1] Implementar `src/brands/layer2_unique.py` — frase exata para Brazino777 e Superbet
- [X] T051 [US1] Implementar `src/brands/layer3_ambiguous.py` — coocorrência por proximidade com termos da categoria **mais** lista de exclusão, tratando nominalmente os cinco casos da tabela em `contracts/brand-identifier.md`. Comentar em português as regras de negócio não óbvias (Princípio VIII)
- [X] T052 [US1] Implementar `src/brands/pipeline.py` — aplica as camadas em ordem, para na primeira que decide, e grava `layer`, `method`, `confidence`, `above_floor` e `floor_version` (depende de T049–T051)
- [X] T053 [US1] Aplicar o piso de confiança **único e igual para todas as marcas** em `src/brands/pipeline.py`; piso por marca é proibido porque tornaria os denominadores do SoV não comparáveis (FR-004a)

### Avaliação e portão de regressão

- [ ] T054 [US1] Implementar `src/evaluation/metrics.py` — precisão, revocação e F1 **por marca e por camada**, calculados sobre a mesma população que alimenta as métricas (apenas acima do piso)
- [ ] T055 [US1] Implementar `src/evaluation/report.py` — gera `docs/evaluation_report.md` com os números, versão do identificador, versão do conjunto e data da medição
- [ ] T056 [US1] Criar `src/evaluation/history.json` e o teste `tests/unit/test_precision_regression.py` — **reprova a suíte se a precisão cair em qualquer marca** frente à versão anterior (Princípio IV)
- [X] T057 [P] [US1] Escrever `tests/unit/test_layer1_domain.py`, `test_layer2_unique.py` e `test_layer3_ambiguous.py` com os casos ambíguos nominais: "reais" moeda, "Reals" clube, "bingo" jogo, "bingo!" interjeição, "aposta esportiva" expressão, veículo com "Esportiva" no nome
- [ ] T058 [US1] Escrever `tests/unit/test_confidence_floor.py` — menções abaixo do piso permanecem consultáveis e nunca são apagadas (FR-004c); nenhuma delas entra em métrica
- [ ] T149 [US1] Implementar o portão de publicação em `src/evaluation/gate.py` — bloquear a materialização de qualquer mart de métrica de negócio quando não existir precisão vigente documentada para o identificador que o alimenta, e testá-lo em `tests/unit/test_publication_gate.py` (FR-007)
- [ ] T059 [US1] Adicionar a tarefa de avaliação de precisão ao `dags/daily_mentions.py` e ao workflow de CI

**Checkpoint**: US1 completa. Existe um identificador de marca com qualidade conhecida e um
relatório publicável — **o principal artefato da apresentação**. Nenhuma métrica de negócio ainda.

---

## Phase 5: User Story 2 — Share of Voice Diário (P2)

**Goal**: série diária de volume absoluto e dos dois shares de voz nomeados, para as 7 marcas, em
3 meses.

**Independent Test**: consultar a série e verificar que cada ponto expõe numerador, denominador,
recorte e regra de categoria.

- [ ] T060 [US2] Implementar `src/ingestion/gdelt_doc.py` — construção de query por camada e por modo conforme `contracts/gdelt-doc-api.md`, com os operadores **dentro do valor de `query`**
- [ ] T061 [US2] Implementar a coleta `TimelineVolRaw` por marca e da categoria em `src/ingestion/gdelt_doc.py` — numerador e denominador (D7)
- [ ] T062 [US2] Implementar a extração do GKG para o corpus da categoria em `src/ingestion/bigquery_client.py`, materializando em MinIO na primeira passada (regra de extração única)
- [ ] T063 [P] [US2] Criar `dbt/models/staging/stg_gdelt_timeline_volume.sql` (view, 1:1 com a fonte)
- [ ] T064 [P] [US2] Criar `dbt/models/staging/stg_gkg_documents.sql` (view)
- [ ] T141 [US2] Criar `dbt/models/staging/br_articles.sql` — camada bronze incremental com merge sobre `article_url`, deduplicando captura: a mesma URL capturada N vezes vira 1 linha (modelo previsto em `data-model.md` e sem tarefa até aqui)
- [ ] T065 [US2] Criar `dbt/models/intermediate/int_category_coverage.sql` — denominador pela **união** de taxonomia da fonte e lista de termos, gravando `inclusion_origin` (`taxonomy`|`term_list`|`both`) e `term_list_version` (FR-013)
- [ ] T066 [US2] Criar `dbt/models/marts/fct_brand_mentions_daily.sql` — incremental com merge sobre `(brand_id, date_key, outlet_key)`, com as medidas `mention_count`, `mentions_below_floor`, `sov_global`, `sov_brasil`, `denominator_global`, `denominator_brasil`
- [ ] T146 [US2] Garantir o *date spine* em `dbt/models/marts/fct_brand_mentions_daily.sql` — cruzar `dim_brand` × `dim_date` para que dia sem menção apareça como **zero explícito e não como lacuna**, e escrever `dbt/tests/assert_no_missing_days.sql` provando a ausência de dias faltantes na janela (FR-016, SC-001)
- [ ] T067 [US2] Criar `dbt/macros/metrics.sql` — definir **uma única vez** volume de menções, share de voz, tom médio ponderado, desvio frente à linha de base e concentração por veículo
- [ ] T068 [US2] Criar `dbt/models/marts/mrt_share_of_voice_daily.sql` com as duas séries nomeadas `sov_global` e `sov_brasil`, mais o volume absoluto que sustenta o recorte Brasil (FR-020b)
- [ ] T069 [US2] Preencher o `description` de **toda** coluna dos marts em `dbt/models/marts/schema.yml` com as ressalvas metodológicas do Princípio VII — é de lá que o dbt docs as publica
- [ ] T070 [P] [US2] Escrever o teste dbt singular `dbt/tests/assert_sov_undefined_when_denominator_zero.sql` — denominador zero produz SoV **indefinido, nunca zero**
- [ ] T071 [P] [US2] Escrever o teste dbt `dbt/tests/assert_sov_within_range.sql` com `dbt_expectations` — `sov` ∈ [0,1] e denominador > 0
- [ ] T072 [US2] Criar `docs/metrics_dictionary.md` com `mede`, `nao_mede`, `limites_de_cobertura` e `normalizacao` para cada métrica, e o teste que reprova métrica com campo vazio (SC-013)
- [ ] T148 [US2] Criar `dbt/models/marts/mrt_denominator_composition.sql` — publicar, por período, a composição do denominador segundo `inclusion_origin` (`taxonomy`, `term_list`, `both`), tornando a sensibilidade do SoV à regra de categoria verificável (FR-013b)
- [ ] T073 [US2] Documentar em `docs/metrics_dictionary.md` que um conteúdo citando N marcas conta como menção para cada uma enquanto o denominador o conta uma vez — **por isso a soma dos SoV pode exceder 100%** (FR-015)

**Checkpoint**: US1 + US2 funcionam. Existe share of voice publicável com precisão documentada.

---

## Phase 6: User Story 3 — Investigação de Pico no Dia (P3)

**Goal**: lista de menções de um dia com veículo, título, idioma, país e link.

**Independent Test**: escolher marca e data e obter a lista completa, com a reconciliação declarada.

- [ ] T074 [US3] Implementar a coleta `ArtList` por marca e por dia em `src/ingestion/gdelt_doc.py`, com `maxrecords=250`
- [ ] T075 [US3] Implementar o fatiamento por subjanela em `src/ingestion/gdelt_doc.py` — quando `truncated_at_max` for verdadeiro, dividir o dia em `startdatetime`/`enddatetime` menores e reconsultar. É a única forma de paginar nesta API
- [ ] T076 [P] [US3] Criar `dbt/models/staging/stg_gdelt_articles.sql` — parse do `raw_body` extraindo `url`, `title`, `domain`, `language`, `sourcecountry`, `seendate`
- [ ] T077 [US3] Criar `dbt/models/intermediate/sl_brand_mentions.sql` com todos os campos de `data-model.md`, incluindo `identification_layer`, `identification_method`, `confidence`, `above_confidence_floor` e `confidence_floor_version`
- [ ] T144 [US3] Adicionar a `dbt/models/intermediate/sl_brand_mentions.sql` a marcação temática de regulação, jogo compulsivo e integridade esportiva como categoria analítica neutra, e escrever `tests/unit/test_compliance_category_no_downstream.py` provando que nenhum mart de segmentação comercial a consome (FR-036, Princípio XII)
- [ ] T078 [US3] Criar `dbt/models/marts/mrt_mentions_detail.sql` com a **coluna de reconciliação** `ArtList` × `TimelineVolRaw`, publicando a diferença em vez de escondê-la (FR-023 conforme decidido em T012)
- [ ] T079 [P] [US3] Escrever `dbt/tests/assert_tone_labeled_as_approximate.sql` — garantir que nenhuma coluna ou descrição use o termo "análise de sentimento" para o indicador de tom (FR-021)
- [ ] T080 [P] [US3] Escrever `tests/unit/test_artlist_slicing.py` — resposta com exatamente 250 artigos dispara o fatiamento

**Checkpoint**: a assessoria consegue investigar um pico e ver quanto do dia foi truncado.

---

## Phase 7: User Story 4 — Distribuição por Veículo, País e Idioma (P4)

**Goal**: saber de onde vem a cobertura de cada marca.

**Independent Test**: consultar as três distribuições e conferir que fecham com o volume absoluto.

- [ ] T081 [US4] Implementar a construção de `dim_outlet` via `sourcecountry:brazil` da DOC 2.0 em `src/ingestion/gdelt_doc.py` — o GKG não tem país da fonte, e este caminho usa a classificação do próprio GDELT a custo zero de BigQuery (D9)
- [ ] T142 [US4] Definir e documentar em `docs/metrics_dictionary.md` a regra de `covers_category`: veículo com pelo menos N conteúdos da categoria no período, com N em `src/common/config.py`. Sem essa regra a US8 inteira fica sem definição
- [ ] T082 [US4] Criar `dbt/models/marts/dim_outlet.sql` com `domain`, `name`, `country` e `covers_category`
- [ ] T083 [US4] Criar `dbt/models/marts/mrt_outlet_distribution.sql` com as distribuições por veículo, país e idioma
- [ ] T084 [P] [US4] Escrever `dbt/tests/assert_distribution_totals_match_volume.sql` — a soma de cada distribuição é igual ao volume absoluto do período (FR-018)
- [ ] T085 [P] [US4] Escrever `dbt/tests/assert_outlet_referential_integrity.sql` — `relationships` de fato para `dim_outlet`

**Checkpoint**: US1–US4 completas. Todas as MUST de análise entregues.

---

## Phase 8: User Story 5 — Idempotência e Regra de Republicação (P5)

**Goal**: reprocessar um intervalo produz estado idêntico; republicação segue regra documentada.

**Independent Test**: `make run DATE=X` duas vezes e `make check-idempotency DATE=X`.

- [ ] T086 [US5] Implementar a deduplicação em `dbt/models/intermediate/int_articles_deduplicated.sql` — chave de negócio `(veiculo_dominio, conteudo_hash)`: o mesmo texto em 40 portais são **40 menções, uma por veículo**; o mesmo texto capturado 2× do mesmo portal é **1 menção** (FR-031)
- [ ] T087 [US5] Documentar a regra de contagem de republicação em `docs/metrics_dictionary.md`
- [ ] T088 [US5] Garantir merge incremental com chave única em `dbt/models/marts/fct_brand_mentions_daily.sql` e documentar a estratégia
- [ ] T089 [US5] Implementar `make check-idempotency` em `Makefile` — compara contagem de linhas e checksum das camadas de consumo entre duas execuções
- [ ] T090 [P] [US5] Escrever `dbt/tests/assert_reprocessing_is_idempotent.sql` (SC-010)
- [ ] T091 [P] [US5] Escrever `tests/unit/test_no_implicit_current_date.py` — varrer `src/`, `dags/` e `dbt/` e reprovar qualquer uso de `now()`, `today()`, `current_date` ou `datetime.now()` em código de pipeline (Princípio IX)
- [ ] T092 [P] [US5] Escrever `dbt/tests/assert_republication_counting.sql` com fixture de republicação conhecida
- [ ] T093 [US5] Escrever `tests/unit/test_add_new_brand.py` — adicionar marca alterando **apenas** `brands.csv` e o conjunto de avaliação, sem tocar na lógica do pipeline (FR-034)

**Checkpoint**: o pipeline sobrevive a correção e reprocessamento sem limpeza manual.

---

## Phase 9: User Story 6 — Frescor e Resultado dos Testes (P6)

**Goal**: o usuário vê procedência antes de levar o número a uma reunião.

**Independent Test**: consultar o painel de estado de cada tabela de consumo.

- [ ] T094 [US6] Localizar na documentação oficial do GDELT o atraso real de publicação e **resolver o `TODO(SLA_FRESHNESS)`** da constituição; registrar a URL que justifica o valor em `docs/adr/0005-sla-freshness.md`
- [ ] T095 [US6] Configurar `source freshness` em `dbt/models/sources.yml` com o SLA calibrado por T094 — verificado na documentação, **não estimado** (Princípio VI)
- [ ] T096 [US6] Criar `dbt/models/marts/mrt_table_status.sql` — data da última atualização bem-sucedida, data lógica processada e resultado da última execução de testes por tabela (FR-024)
- [ ] T097 [US6] Configurar o `dags/daily_mentions.py` para **interromper** o DAG e não escrever a camada seguinte quando qualquer teste falhar (Princípio VI)
- [ ] T098 [P] [US6] Escrever `tests/integration/test_pipeline_halts_on_test_failure.py` — execução com teste falhando termina com código de saída ≠ 0 e sem escrita na camada seguinte
- [ ] T099 [P] [US6] Escrever `tests/unit/test_structured_log_fields.py` — toda execução emite os campos obrigatórios do Princípio XI

**Checkpoint**: todas as MUST (US1–US6) entregues. **Este é o corte mínimo apresentável.**

---

## Phase 10: User Story 7 — Linha de Base Histórica de 12 Meses (P7) · SHOULD

**Goal**: saber se o volume da janela recente é pico ou é normal.

**Independent Test**: consultar a distribuição histórica de 12 meses por marca.

- [ ] T100 [US7] Implementar a extração histórica do GKG em `dags/historical_backfill.py` com as quatro travas ativas e materialização única em MinIO
- [ ] T101 [US7] Criar `dbt/models/intermediate/sl_brand_baseline.sql` com `median_volume`, `mad`, `mad_is_zero`, `weekday` e `baseline_window` por marca
- [ ] T102 [P] [US7] Escrever `dbt/tests/assert_baseline_covers_12_months.sql` (SC-002)
- [ ] T147 [US7] Adicionar ao fim de `dags/historical_backfill.py` a asserção de que a camada bruta contém no mínimo 10 milhões de linhas, falhando o DAG caso contrário (SC-003)
- [ ] T103 [US7] Gerar `docs/cost_report.md` com bytes estimados × bytes faturados por consulta; divergência grande indica dry run mal calibrado

**Checkpoint**: linha de base pronta, habilitando a detecção de anomalia.

---

## Phase 11: User Story 8 — Espaço em Branco de Mídia (P8) · SHOULD

**Goal**: lista nominal de veículos que cobrem apostas e nunca citaram as marcas próprias.

**Independent Test**: gerar a lista e conferir manualmente uma amostra de 20 veículos.

- [ ] T104 [US8] Criar `dbt/models/marts/mrt_media_whitespace.sql` — anti-join de `dim_outlet.covers_category` contra menções de marca própria, aplicando o limiar mínimo de conteúdos por veículo (FR-038)
- [ ] T105 [US8] Distinguir "nunca citou" de "citou pouco" em `mrt_media_whitespace.sql` e escrever a ressalva de que ausência de menção na fonte **não prova** ausência de publicação (FR-039)
- [ ] T106 [P] [US8] Escrever `dbt/tests/assert_whitespace_excludes_low_volume_outlets.sql`
- [ ] T107 [US8] Conferir manualmente 20 veículos da lista e registrar o resultado em `docs/whitespace_validation.md` (SC-015)

**Checkpoint**: a entrega mais acionável do projeto está pronta.

---

## Phase 12: User Story 9 — Indicador de Tom ao Longo do Tempo (P9) · SHOULD

**Goal**: distinguir crescimento de exposição favorável de crescimento por crise.

**Independent Test**: consultar a série de tom por marca com a ressalva presente.

- [ ] T108 [US9] Implementar a coleta `TimelineTone` em `src/ingestion/gdelt_doc.py`
- [ ] T109 [P] [US9] Criar `dbt/models/staging/stg_gdelt_timeline_tone.sql`
- [ ] T110 [US9] Adicionar `avg_tone` a `fct_brand_mentions_daily.sql`, excluindo menções sem indicador e **informando a quantidade excluída** (FR/US9 cenário 2)
- [ ] T111 [P] [US9] Escrever `dbt/tests/assert_tone_excluded_count_reported.sql`

---

## Phase 13: User Story 10 — Detecção de Anomalia (P10) · SHOULD

**Goal**: sinalizar dia anômalo frente à linha de base da própria marca.

**Independent Test**: injetar dia sintético atípico e verificar que é pego; dias normais não.

- [ ] T112 [US10] Implementar `src/anomaly/detector.py` — desvio da mediana da própria marca em mais de **N desvios absolutos medianos (MAD)**, com ajuste de sazonalidade semanal e N configurável em `config.py`
- [ ] T113 [US10] Tratar explicitamente o caso `mad_is_zero` em `src/anomaly/detector.py`, sem sinalizar todo dia não nulo como anomalia (FR-027b)
- [ ] T114 [US10] Criar `dbt/models/marts/mrt_anomalies.sql` com `brand_id`, `date`, magnitude em MAD, N e janela vigentes, e `review_status`
- [ ] T115 [P] [US10] Escrever `tests/unit/test_anomaly.py` — dia sintético atípico é sinalizado; dia dentro do limiar não é; marca estruturalmente maior não é sinalizada por porte; `mad = 0` é tratado (SC-016)
- [ ] T116 [US10] Adicionar a tarefa de detecção ao `dags/daily_mentions.py`

---

## Phase 14: User Story 11 — Hipótese de Causa da Anomalia (P11) · SHOULD

**Goal**: cada anomalia vem com hipótese rotulada como não verificada.

**Independent Test**: gerar a hipótese de uma anomalia conhecida e verificar rótulo e referências.

- [ ] T117 [US11] Implementar `src/ai/cache.py` — cache determinístico por `input_hash`, com `prompt_version` gravada em toda saída
- [ ] T118 [US11] Criar `src/ai/prompts/anomaly_explainer_v1.md` versionado
- [ ] T119 [US11] Implementar `src/ai/fallback.py` — resumo determinístico por regras (N veículos e títulos mais frequentes do dia, sem interpretação). **É o que roda nos testes** (Princípio XIII)
- [ ] T120 [US11] Implementar o explicador em `src/ai/anomaly_explainer.py` com saída validada por esquema `pydantic` estrito: `{hypothesis, supporting_mention_ids[], status: "nao_verificada"}`; saída inválida cai no fallback
- [ ] T121 [US11] Implementar o desambiguador da Camada 4 em `src/brands/layer4_ai.py`, com fila de revisão humana para baixa confiança
- [ ] T122 [US11] Medir o ganho da Camada 4 frente à linha de base por regras no conjunto de avaliação e publicar em `docs/evaluation_report.md` — **sem ganho documentado, o componente não entra em produção** (Princípio XIII)
- [ ] T123 [P] [US11] Escrever `tests/unit/test_ai_components.py` — suíte inteira roda em modo fallback; mesma entrada 2× ⇒ 1 chamada; saída fora do esquema cai no fallback; prompt alterado gera nova versão
- [ ] T124 [P] [US11] Escrever `tests/unit/test_hypothesis_has_no_downstream.py` — a hipótese **não tem aresta de saída** para nenhum fato ou dimensão na linhagem do dbt

**Checkpoint**: todas as SHOULD entregues.

---

## Phase 15: Portão do Dia 5 — COULD

**⚠️ Só iniciar se todas as MUST estiverem fechadas no dia 5.** Ordem de corte declarada na spec.

- [ ] T125 [COULD] Verificar na documentação oficial a API de Pageviews da Wikimedia (endpoint, exigência de User-Agent, limites, licença) e registrar em `docs/adr/0006-wikimedia-pageviews.md`
- [ ] T126 [COULD] Implementar o cruzamento de picos com atenção sobre propriedades esportivas patrocinadas, apresentado como **correlação, nunca como causa** (FR-026)
- [ ] T127 [COULD] Implementar painel visual navegável
- [ ] T128 [COULD] Implementar a métrica agregada de risco reputacional para Compliance

---

## Phase 16: Polish & Cross-Cutting

- [ ] T129 Estender `tests/offline/test_full_reconstruction.py` (criado em T150) para cobrir **todas** as camadas finais a partir da zona bruta com a rede desabilitada (SC-008, Princípio III)
- [ ] T143 [P] Escrever `tests/unit/test_no_causal_language.py` — varrer descrições de coluna, nomes de métrica, `docs/` e o roteiro de demo, reprovando linguagem causal ("causou", "por causa de", "gerou", "levou a") e o termo "análise de sentimento" aplicado ao indicador de tom (FR-021, FR-026, Princípio VII)
- [ ] T130 [P] Escrever o README com problema de negócio, diagrama de arquitetura, tabela de decisões com alternativas descartadas, dicionário de métricas com ressalvas, relatório de precisão, **atribuição e licença do GDELT** (citação + link, exigidos), setup passo a passo e roteiro de demo
- [ ] T131 [P] Documentar em `README.md` a decisão de portabilidade S3: `endpoint_url` configurável torna a migração para S3 real uma troca de variável de ambiente
- [ ] T132 [P] Criar `dbt/seeds/spa_mf_authorized.csv` com razão social, CNPJ e domínio autorizado das 7 marcas, com `data_de_referencia` e URL da consulta (plano B de T010)
- [ ] T133 [P] Enriquecer `dim_brand.sql` com os campos regulatórios do seed da SPA/MF
- [ ] T134 Publicar `dbt docs` como site estático gratuito via GitHub Pages no workflow de merge
- [ ] T135 [P] Documentar em `README.md` a convenção de idioma: documentação e comentários em português do Brasil, objetos técnicos em inglês
- [ ] T136 Finalizar `docs/demo_script.md` e **ensaiar cronometrado em 10 minutos com a rede desligada** (SC-012, Princípio III)
- [ ] T137 Executar `quickstart.md` inteiro em máquina limpa e cronometrar — meta < 30 minutos (SC-011)
- [ ] T138 Revisar que 100% dos modelos de consumo têm teste automatizado e todos passam (SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Fase 1 (Verificações)**: sem dependências. **BLOQUEIA TUDO** — inclusive o Setup de código de produção
- **Fase 2 (Setup)**: depende da Fase 1
- **Fase 3 (Foundational)**: depende da Fase 2. **BLOQUEIA todas as histórias**
- **Fases 4–14 (Histórias)**: dependem da Fase 3
- **Fase 15 (COULD)**: portão do dia 5, depende de todas as MUST fechadas
- **Fase 16 (Polish)**: depende das histórias desejadas

### User Story Dependencies

- **US1 (P1)**: independente após a Fase 3. **É o MVP**
- **US2 (P2)**: independente tecnicamente, mas **não publicável sem US1** (FR-007: nenhuma métrica sem precisão documentada)
- **US3, US4 (P3, P4)**: dependem de US2 para reconciliação e fechamento de totais
- **US5, US6 (P5, P6)**: independentes; podem correr em paralelo com US3/US4
- **US7 (P7)**: independente; habilita US10
- **US8 (P8)**: depende de US4 (`dim_outlet`)
- **US9 (P9)**: depende de US2
- **US10 (P10)**: depende de US7
- **US11 (P11)**: depende de US10

### Parallel Opportunities

- Fase 1: T002, T003, T005–T010 em paralelo
- Fase 2: T014, T015, T016, T019–T024 em paralelo
- Fase 3: T027, T037–T042 em paralelo após T025/T026
- US1: T049 e T050 em paralelo; T057 em paralelo com T054/T055
- US5, US6, US7 podem correr em paralelo entre si

---

## Parallel Example: User Story 1

```bash
# Camadas independentes de identificação, arquivos diferentes:
Task: "Implementar src/brands/layer1_domain.py — âncora de domínio .bet.br"
Task: "Implementar src/brands/layer2_unique.py — frase exata para Brazino777 e Superbet"

# Testes por camada, arquivos diferentes:
Task: "tests/unit/test_layer1_domain.py"
Task: "tests/unit/test_layer2_unique.py"
Task: "tests/unit/test_layer3_ambiguous.py"
```

---

## Implementation Strategy

### Mapa de 7 dias (Princípio XIV)

| Dia | Escopo | Portão |
|-----|--------|--------|
| **1** | Fase 1 (verificações) + Fase 2 (setup) + `demo_script.md` esqueleto | Se V3 estourar o orçamento, aplicar plano B **antes de seguir** |
| **2** | Fase 3 (foundational) — travas de custo e cidadania testadas | Testes T029, T031, T032 passando |
| **3** | Fase 4 — US1 completa, incluindo a rotulagem das 300 menções | `make eval` produz o relatório |
| **4** | Fases 5–7 — US2, US3, US4 | **Congelamento de ferramentas ao fim do dia** |
| **5** | Fases 8–9 — US5, US6. **Todas as MUST fechadas** | Portão do COULD: abre só se as MUST estiverem fechadas |
| **6** | Fases 10–14 — SHOULD, na ordem P7 → P8 → P9 → P10 → P11 | Cortar da última para a primeira se o tempo apertar |
| **7** | Fase 16 — polish, README, ensaio cronometrado da demo | Teste, documentação e demo **nunca** são cortados |

### MVP First

1. Fase 1 → Fase 2 → Fase 3
2. Fase 4 (US1) → **PARE E VALIDE**: `make eval` produz precisão por marca e por camada
3. Este já é um portfólio defensável: um identificador de marca com qualidade medida vale mais que
   um painel bonito com números não auditados

### Ordem de corte sob pressão de prazo

COULD primeiro (T125–T128, nesta ordem), depois SHOULD da última para a primeira
(US11 → US10 → US9 → US8 → US7). **Nunca** cortar: T129 (reconstrução offline), qualquer teste,
T130 (README), T136 (roteiro de demo).

---

## Notes

- `[P]` = arquivos diferentes, sem dependência pendente
- Commit após cada tarefa ou grupo lógico
- Toda função pública com type hints; docstring de módulo explicando o porquê (Princípio VIII)
- Regras de negócio não óbvias comentadas em português
- Complexidade adicional exige justificativa escrita em ADR ou no PR
- Cada PR passa pelo checklist de 14 itens da constituição antes do merge
