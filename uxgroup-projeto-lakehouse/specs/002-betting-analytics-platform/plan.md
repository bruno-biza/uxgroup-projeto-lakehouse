# Implementation Plan: Plataforma Analítica de Apostas Esportivas

**Branch**: `002-betting-analytics-platform` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-betting-analytics-platform/spec.md`

## Summary

Um gerador Python produz lotes diários sintéticos em CSV (apostadores, eventos, apostas,
transações) com defeitos injetados em proporções configuráveis. Um carregador Python envia os
arquivos para um stage interno do Snowflake e materializa a camada RAW sem transformação. O dbt
limpa, tipa, deduplica e desvia os registros inválidos para modelos de quarentena em STAGING, e
constrói dimensões, fatos incrementais e quatro agregados diários em MARTS — GGR por esporte,
engajamento, fluxo financeiro e qualidade do lote. Um Airflow local orquestra a sequência inteira
numa DAG diária de seis tarefas, com testes de dados bloqueando a passagem entre camadas.

Três decisões de projeto merecem destaque porque não são o caminho ingênuo:

1. **RAW é substituída por lote, não apenas apendada.** Depender só do histórico de carga do
   `COPY INTO` quebra a idempotência quando o conteúdo do arquivo muda entre execuções da mesma
   data. A ingestão apaga as linhas daquele lote e recarrega com `FORCE=TRUE`. Ver
   [research.md](./research.md#d1) — inclui a reconciliação com o Princípio III.
2. **Fatos são incrementais; agregados diários são full-refresh.** É o que faz `FR-019b`
   (recalcular datas afetadas quando uma pendente resolve) funcionar sem maquinaria de
   backfill — em lotes de dezenas de milhares de linhas, reconstruir os agregados custa segundos.
3. **dbt vive num virtualenv próprio dentro da imagem do Airflow**, chamado por caminho absoluto
   no `BashOperator`. Instalar dbt-core ao lado do Airflow no mesmo interpretador colide nas
   restrições de dependência de ambos.

### Sequenciamento (3 dias)

O Princípio IX manda fechar o fluxo antes de refinar. A ordem é vertical, não por camada:

- **Dia 1 — esqueleto que atravessa**: setup do Snowflake, gerador mínimo (sem defeitos), ingestão
  RAW, um `stg_apostas`, um `agg_ggr_diario_esporte`, DAG rodando ponta a ponta. Fim do dia 1: um
  número de GGR sai do Snowflake por comando único.
- **Dia 2 — a tese do projeto**: injeção de defeitos, validação e quarentena, `agg_qualidade_lote`,
  suíte de testes dbt, fatos incrementais com merge, idempotência provada por teste de dupla
  execução.
- **Dia 3 — completar e blindar**: agregados de engajamento e financeiro, dimensões, README,
  diagrama, ensaio da demo. Dashboard só se sobrar tempo e nunca antes do ensaio.

## Technical Context

**Language/Version**: Python 3.11 (geração, ingestão, testes); SQL dialeto Snowflake (transformação)

**Primary Dependencies**: Faker (dados sintéticos), snowflake-connector-python (PUT/COPY INTO),
dbt-core + dbt-snowflake 1.8 (transformação), Apache Airflow 2.9 (orquestração), Docker Compose
(ambiente local), pytest + ruff (qualidade de código)

**Storage**: Snowflake trial — database `BETS`, schemas `RAW`, `STAGING`, `MARTS`; stage interno
`RAW.STG_LOTES`. Arquivos CSV intermediários em volume local montado no contêiner do Airflow.

**Testing**: pytest para gerador, ingestão e determinismo de seed; `dbt test` para dados —
genéricos (`unique`, `not_null`, `accepted_values`, `relationships`) e singulares para as regras de
negócio de `FR-013` a `FR-016`

**Target Platform**: Docker Compose em máquina de desenvolvimento (Linux, macOS ou Windows com WSL2);
Snowflake como único serviço remoto

**Project Type**: Pipeline de dados em lote (batch), com CLIs Python e projeto dbt

**Performance Goals**: um lote de ~50 mil linhas atravessa a DAG inteira em menos de 5 minutos, para
caber no orçamento de 10 minutos de demo (`SC-007`) com folga para narração

**Constraints**: warehouse XSMALL com `AUTO_SUSPEND = 60` (Princípio I); nenhum recurso pago;
nenhum passo manual entre tarefas (`FR-018`); credenciais só por variável de ambiente
(Princípio VIII); nenhum dado pessoal real (Princípio VI)

**Scale/Scope**: 4 entidades de origem, 4 tipos de defeito injetado, ~10 modelos dbt, 1 DAG de 6
tarefas, ~30 testes de dados. Volume padrão de 50 mil linhas por lote, configurável.

## Constitution Check

*GATE: avaliado contra a constituição v2.0.0. Reavaliado após o desenho da Fase 1 — resultado
idêntico.*

| Princípio | Como este plano satisfaz | Veredito |
|---|---|---|
| I. Custo Zero | Snowflake trial, warehouse XSMALL, `AUTO_SUSPEND = 60` declarado no SQL de setup versionado. Airflow, dbt, Postgres e Docker rodam locais. Nenhum serviço cobrado. | PASS |
| II. Pipeline ponta a ponta | `make setup` faz o bootstrap do Snowflake uma vez; `make run DATA=YYYY-MM-DD` dispara a DAG inteira. Nenhum passo manual entre tarefas. | PASS |
| III. Medallion | `RAW` recebe o CSV sem transformação, só com metadados de carga; `STAGING` limpa e tipa; `MARTS` agrega. Nenhum modelo de MARTS referencia RAW. | PASS com nuance — ver Complexity Tracking |
| IV. Idempotência | Data lógica vem do `{{ ds }}` do Airflow e desce como parâmetro para o gerador e como `--vars` do dbt. RAW é substituída por lote; fatos usam `merge` com `unique_key`. Nenhum `current_date` em código de pipeline. | PASS |
| V. Qualidade como bloqueio | `dbt_test_staging` e `dbt_test_marts` são tarefas próprias da DAG; falha aborta e a tarefa seguinte não roda. Todo modelo de STAGING e MARTS entra na suíte. | PASS |
| VI. Dados sintéticos | Faker com seed fixa em configuração versionada; CSV com ordenação e formatação determinísticas para que o checksum se repita. Nenhum campo com dado pessoal real. | PASS |
| VII. Python + SQL | Gerador e carregador em Python com type hints e docstring de módulo; toda transformação analítica em SQL dentro do dbt. | PASS |
| VIII. Segredos fora do código | `.env` no `.gitignore`, `.env.example` versionado sem valores; Compose injeta as variáveis nos contêineres via `env_file`; `profiles.yml` do dbt lê de `env_var()`. | PASS |
| IX. Simplicidade | `BashOperator` em vez de Cosmos; agregados full-refresh em vez de backfill incremental; nenhuma otimização antes do fluxo verde. Supersede o ADR 0003 do escopo antigo. | PASS |
| X. Documentação é entregável | README com diagrama, pré-requisitos e passo a passo; [quickstart.md](./quickstart.md) é o roteiro de validação executável. | PASS |

**Observabilidade mínima** (Restrições Técnicas Adicionais): o carregador e o gerador emitem log
estruturado com data lógica, linhas lidas e escritas e duração; `ruff` com a regra `T20` mantém o
`print` proibido fora dos CLIs de verificação.

**Nenhuma violação injustificada.** A única tensão registrada está em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-betting-analytics-platform/
├── plan.md              # Este arquivo
├── spec.md              # Especificação com as 5 clarificações integradas
├── research.md          # Fase 0 — decisões técnicas e alternativas rejeitadas
├── data-model.md        # Fase 1 — RAW, STAGING, MARTS, quarentena, regras de validação
├── quickstart.md        # Fase 1 — roteiro de validação ponta a ponta
├── contracts/
│   ├── cli.md           # Contrato das CLIs do gerador e do carregador
│   ├── csv-batch.md     # Formato do lote na fronteira gerador → ingestão
│   └── marts.md         # Contrato das tabelas de métricas expostas ao analista
├── checklists/
│   └── requirements.md  # Checklist de qualidade da spec (16/16)
└── tasks.md             # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
generator/               # Geração sintética (Python)
├── __init__.py
├── cli.py               # Entrada: --data-lote, --volume, --taxa-*, --seed, --saida
├── config.py            # Perfil do lote: volumes por entidade e taxas de defeito
├── entidades.py         # Construção de apostadores, eventos, apostas, transações
├── defeitos.py          # Injeção dos 4 defeitos em proporções configuráveis
└── escrita.py           # Escrita CSV determinística (ordem, formatação, checksum)

ingestion/               # Carga para a camada RAW (Python)
├── __init__.py
├── cli.py               # Entrada: --data-lote, --diretorio
├── snowflake_client.py  # Conexão, PUT para stage interno, COPY INTO
└── carga_raw.py         # Substituição por lote + metadados de origem

common/                  # Compartilhado por generator/ e ingestion/
├── __init__.py
├── config.py            # Leitura de variáveis de ambiente, sem valores default sensíveis
└── logging.py           # Log estruturado com os campos obrigatórios da constituição

snowflake_setup/         # Bootstrap do warehouse (SQL versionado)
├── 01_warehouse.sql     # WH XSMALL, AUTO_SUSPEND 60, AUTO_RESUME
├── 02_database.sql      # BETS + schemas RAW, STAGING, MARTS
├── 03_stage.sql         # Stage interno e file format CSV
└── 04_raw_tables.sql    # DDL das tabelas RAW com colunas de metadados

dbt_bets/                # Projeto dbt
├── dbt_project.yml
├── profiles.yml         # Credenciais via env_var(), nenhum valor literal
├── models/
│   ├── staging/         # stg_* (limpos) e stg_*_rejeitadas (quarentena) + schema.yml
│   └── marts/           # dim_*, fct_*, agg_* + schema.yml
└── tests/               # Testes singulares das regras de negócio

airflow/
├── Dockerfile           # Imagem estendida: venv isolado com dbt-snowflake
└── dags/
    └── pipeline_bets.py # DAG diária de 6 tarefas

tests/                   # pytest
├── unit/                # Defeitos, determinismo de seed, escrita CSV
└── integration/         # Dupla execução do mesmo lote, contagens de quarentena

docs/
├── arquitetura.md       # Diagrama e linhagem
├── metricas.md          # Dicionário: o que cada métrica inclui e exclui (FR-017)
├── demo_script.md       # Roteiro da apresentação
└── adr/                 # Decisões; as do escopo antigo ficam como histórico superado

docker-compose.yml       # Postgres + Airflow (webserver, scheduler, init)
Makefile                 # setup, run, test, clean
pyproject.toml           # Dependências e configuração de ruff/pytest
.env.example             # Chaves esperadas, sem valores
```

**Structure Decision**: adotada a estrutura pedida no input — `generator/`, `ingestion/`,
`snowflake_setup/`, `dbt_bets/`, `airflow/dags/`, `docs/` — com duas adições e uma remoção.

*Adições*: `common/` existe porque log estruturado e leitura de configuração são exigidos pela
constituição e usados pelos dois módulos Python; duplicá-los seria pior do que ter um pacote de
três arquivos. `tests/` existe porque `SC-002` e `SC-005` só são demonstráveis por teste
automatizado.

*Remoção*: o repositório carrega hoje ~1.600 linhas do escopo anterior (GDELT, BigQuery, MongoDB,
MinIO) que conflitam com a constituição v2.0.0. São descartados `src/ai/`, `src/anomaly/`,
`src/brands/`, `src/evaluation/`, `src/ingestion/`, `evaluation_set/`, `infra/terraform/`, os seeds
de marcas em `dbt/seeds/` e os serviços `mongodb`, `minio` e `minio-init` do `docker-compose.yml`.
`src/common/logging.py` e `src/common/config.py` migram para `common/`. O `specs/001-*` e os ADRs
0001–0005 permanecem como registro histórico, marcados como superados.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| RAW recebe `DELETE` das linhas do lote antes do recarregamento, embora o Princípio III diga que RAW é append-only e nunca editada | `SC-002` exige que reprocessar não altere resultado. O histórico de carga do `COPY INTO` só reconhece o par nome-do-arquivo + ETag: se o mesmo dia for regerado com volume ou taxa de defeito diferente, o arquivo muda de ETag e é carregado de novo, duplicando linhas em RAW. Sem a substituição por lote, a idempotência é falsa | Confiar apenas no histórico de carga foi rejeitado por não sobreviver à regeração de um lote, que é justamente o que se faz numa demo ao vivo. A leitura do Princípio III que este plano adota é a da spec: o lote é a verdade completa do seu conteúdo bruto e é substituído inteiro, nunca editado linha a linha — nenhum `UPDATE` toca RAW, e o conteúdo continua sendo o CSV como veio, sem transformação. Requer ADR |
| MARTS pode ficar transitoriamente inconsistente entre modelos se um teste reprovar no meio do `dbt build`, enquanto `FR-020a` pede que MARTS fique no estado anterior à execução | dbt não envolve uma execução inteira em transação. Garantir atomicidade de todo o schema exigiria construir em schema paralelo e usar `ALTER SCHEMA ... SWAP WITH` | O swap de schema foi rejeitado porque quebra a continuidade do estado dos modelos incrementais: após o swap, a próxima execução incremental enxergaria as tabelas antigas. Mitigação adotada: `dbt build` intercala modelo e teste com `--fail-fast`, então a falha interrompe antes de os agregados a jusante serem reconstruídos, e o analista continua vendo os agregados do lote anterior, coerentes entre si. O risco residual é `fct_apostas` ficar à frente dos agregados até a reexecução. Documentado em research.md, decisão D3 |
