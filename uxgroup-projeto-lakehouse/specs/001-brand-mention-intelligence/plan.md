# Implementation Plan: Brand Mention Intelligence — Share of Voice de Marcas de Apostas

**Branch**: `001-brand-mention-intelligence` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-brand-mention-intelligence/spec.md`

## Summary

Lakehouse local de custo zero que mede o share of voice de 7 marcas de apostas na cobertura
jornalística do GDELT, com identificação de marca em 4 camadas de confiança decrescente e precisão
medida contra um conjunto rotulado versionado.

Duas fontes complementares, escolhidas por limitação confirmada e não por preferência: a **DOC 2.0
API** cobre a janela ativa (sua janela móvel de 3 meses é exatamente o escopo de SC-001) e o
**GKG particionado no BigQuery** cobre a linha de base de 12 meses e o corpus da categoria (a DOC
2.0 não alcança 12 meses). Zona bruta em MongoDB e MinIO, transformação em dbt sobre BigQuery,
orquestração em Airflow com Cosmos, tudo em Docker Compose subindo com um comando.

O entregável central não é o painel: é o **relatório de precisão da identificação de marca**,
tratado com a mesma prioridade dos modelos de dados, conforme Princípio IV.

## Technical Context

**Language/Version**: Python 3.11 (ingestão, identificação de marca, avaliação, detecção de
anomalia, utilitários); SQL para transformação analítica

**Primary Dependencies**: `requests` + cliente HTTP próprio (não `gdeltdoc` — ver D2 em
[research.md](./research.md)), `google-cloud-bigquery`, `pymongo`, `boto3`, `dbt-core` +
`dbt-bigquery`, `apache-airflow`, `astronomer-cosmos`, `pytest`, `pydantic` (validação de esquema
estrito da saída de IA)

**Storage**:
- MongoDB (contêiner) — landing zone dos JSON crus da DOC 2.0 com metadados de captura
- MinIO / object storage S3-compatível (contêiner) — Parquet particionado por data; acesso por
  `boto3` com `endpoint_url` configurável, de modo que migrar para S3 real seja troca de variável
  de ambiente
- PostgreSQL (contêiner) — metastore do Airflow e serving relacional das tabelas pequenas
- BigQuery (free tier) — bronze, silver e gold, datasets separados por camada e ambiente,
  particionado por data e clusterizado por marca

**Testing**: pytest (unidade e integração offline), testes nativos do dbt +
`dbt-expectations`/`dbt-utils`, suíte executável com rede desabilitada

**Target Platform**: notebook pessoal Linux/WSL2 com Docker; CI em GitHub Actions (free)

**Project Type**: pipeline de dados em lote (lakehouse em camadas), sem front-end próprio

**Performance Goals**: ciclo diário incremental completo em < 20 min (SC-006, ver ressalva em
Riscos R2); backfill inicial em DAG separado, sem SLA de 20 min

**Constraints**: custo financeiro **zero absoluto**; orçamento auto-imposto de **200 GiB** varridos
no BigQuery no projeto inteiro (20% do 1 TiB mensal gratuito); 1 requisição / 5 s em série contra
a DOC 2.0; nenhuma ferramenta nova depois do dia 4; suíte de testes roda offline

**Scale/Scope**: 7 marcas, janela ativa de 3 meses diária, linha de base de 12 meses, ≥ 10 M linhas
na camada bruta, conjunto de avaliação ≥ 300 menções rotuladas, 11 histórias P1–P11

## Constitution Check

*GATE: avaliado antes da Fase 0 e reavaliado após a Fase 1.*

| Princípio | Como o plano atende | Status |
|-----------|--------------------|--------|
| **I. Custo zero com trava técnica** (NN) | 4 travas cumulativas em vez de 3: cota diária de bytes no projeto GCP, `maximum_bytes_billed` por job lido de config central, dry run obrigatório com bytes em log, e validação programática de `_PARTITIONTIME` antes do envio. Extração única materializada em MinIO. Orçamento total de 200 GiB | PASS |
| **II. Cidadania de API** (NN) | Cliente próprio com UA identificando projeto e contato, backoff exponencial com jitter, teto de tentativas, timeout, limite de requisições por execução, série por padrão a 1 req/5 s, cache em disco por hash de requisição | PASS |
| **III. Imutabilidade da zona bruta** (NN) | Resposta gravada byte a byte em MongoDB antes de qualquer parse; extração do BigQuery materializada em Parquet imutável; teste de reconstrução com rede desabilitada | PASS |
| **IV. Precisão é métrica** (NN) | Conjunto rotulado ≥ 300 versionado, avaliador que calcula precisão/revocação/F1 por marca **e por camada**, relatório gerado automaticamente, teste que reprova em regressão | PASS |
| **V. Lakehouse em camadas** | landing (Mongo + MinIO) → bronze → silver → gold em datasets BigQuery separados; Cosmos expõe a linhagem por modelo | PASS |
| **VI. Qualidade como portão** | Testes dbt de unicidade, not-null, relacionamento; dedup testada; freshness com SLA da documentação da fonte; falha interrompe o DAG | PASS com pendência: `TODO(SLA_FRESHNESS)` |
| **VII. Honestidade metodológica** (NN) | Ressalvas escritas no `description` de cada coluna de mart, logo aparecem no dbt docs; dicionário com `mede`/`nao_mede`/`limites_de_cobertura` |  PASS |
| **VIII. Python-first e legibilidade** | Python para ingestão/orquestração, SQL para transformação; type hints, docstrings, comentários de regra de negócio em português | PASS |
| **IX. Idempotência** | Data lógica do Airflow passada explicitamente ao dbt; fatos incrementais com chave única e merge; teste de dupla execução | PASS — **depende de D4** (sandbox bloqueia DML) |
| **X. Tudo como código** | Terraform para datasets/tabelas/permissões; Docker Compose + Makefile de um comando; ADRs em `docs/adr/`, inclusive de ferramenta descartada | PASS |
| **XI. Observabilidade** | Log estruturado com data lógica, linhas lidas/escritas, bytes estimados **e** faturados, duração, resultado de testes, falhas externas; dbt docs com linhagem gerada | PASS |
| **XII. Ética e conformidade** | Nenhum dado pessoal; apenas interfaces públicas oficiais; SPA/MF por seed transcrito e não por raspagem; licença e atribuição do GDELT no README | PASS |
| **XIII. IA com rastreabilidade** | Dois componentes, ambos com cache, prompt versionado, saída validada por esquema estrito e **fallback determinístico que é o que roda nos testes**; IA só entra se superar a linha de base por regras | PASS |
| **XIV. Escopo blindado** (NN) | MUST/SHOULD/COULD já classificados na spec; portão do dia 5 para o COULD; congelamento de ferramentas no dia 4 | PASS |

**Resultado do gate**: PASS, com duas pendências rastreadas (`TODO(SLA_FRESHNESS)` e a decisão
D4 sobre billing) e **dois conflitos spec × realidade** registrados em Riscos, que exigem decisão
do autor antes de `/speckit.tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/001-brand-mention-intelligence/
├── plan.md              # Este arquivo
├── spec.md              # Especificação
├── research.md          # Fase 0 — verificação das fontes contra documentação oficial
├── data-model.md        # Fase 1 — entidades, camadas, esquema estrela
├── quickstart.md        # Fase 1 — como subir e validar
├── contracts/           # Fase 1 — contratos das interfaces externas e internas
│   ├── gdelt-doc-api.md
│   ├── bigquery-gkg.md
│   ├── brand-identifier.md
│   └── ai-components.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
.
├── Makefile                     # up, down, test, backfill, docs, eval — um comando cada
├── docker-compose.yml           # airflow, postgres, mongodb, minio
├── .env.example                 # chaves esperadas, sem valores
│
├── src/
│   ├── ingestion/
│   │   ├── http_client.py       # UA, backoff+jitter, teto, timeout, limite, cache — Princípio II
│   │   ├── gdelt_doc.py         # construção de query, modos ArtList/TimelineVolRaw/TimelineTone
│   │   ├── bigquery_client.py   # dry run, maximum_bytes_billed, guarda de _PARTITIONTIME
│   │   └── landing.py           # persistência crua em MongoDB + Parquet em MinIO
│   ├── brands/
│   │   ├── registry.py          # cadastro de marcas versionado
│   │   ├── layer1_domain.py     # âncora de domínio .bet.br
│   │   ├── layer2_unique.py     # nome único por frase exata
│   │   ├── layer3_ambiguous.py  # proximidade + lista de exclusão
│   │   ├── layer4_ai.py         # desambiguação assistida, com fallback determinístico
│   │   └── pipeline.py          # orquestra as camadas, grava método e confiança
│   ├── evaluation/
│   │   ├── dataset.py           # carga do conjunto rotulado
│   │   ├── metrics.py           # precisão, revocação, F1 por marca e por camada
│   │   └── report.py            # relatório automático publicado com a documentação
│   ├── anomaly/
│   │   └── detector.py          # mediana móvel + MAD + sazonalidade semanal
│   ├── ai/
│   │   ├── cache.py             # cache determinístico por entrada
│   │   ├── prompts/             # prompts versionados
│   │   └── fallback.py          # regras determinísticas — o que roda nos testes
│   └── common/
│       ├── logging.py           # log estruturado — nunca print
│       └── config.py            # teto de bytes, limites, pisos — configuração central
│
├── dags/
│   ├── daily_mentions.py        # ciclo diário incremental
│   └── historical_backfill.py   # esporádico, travas de custo, nunca no ciclo diário
│
├── dbt/
│   ├── models/
│   │   ├── staging/             # views, 1:1 com a fonte
│   │   ├── intermediate/        # dedup, normalização de veículo, camadas de marca, baseline
│   │   └── marts/               # esquema estrela
│   ├── macros/                  # métricas definidas uma única vez
│   ├── seeds/                   # cadastro de marcas, lista de termos, SPA/MF datado
│   └── tests/
│
├── evaluation_set/              # conjunto rotulado versionado — entregável de primeira classe
│   ├── labeled_mentions.csv
│   └── README.md                # metodologia de amostragem estratificada
│
├── infra/
│   └── terraform/               # datasets, tabelas, permissões
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── offline/                 # reconstrução com rede desabilitada
│   └── fixtures/                # respostas reais salvas
│
└── docs/
    ├── adr/                     # inclusive ferramentas descartadas
    ├── metrics_dictionary.md
    └── demo_script.md           # existe desde o dia 1, nunca é cortado
```

**Structure Decision**: separação por responsabilidade conforme exigido — orquestração (`dags/`),
ingestão (`src/ingestion/`), identificação de marca (`src/brands/`), transformação (`dbt/`),
componente de IA (`src/ai/`), infraestrutura (`infra/`), testes (`tests/`), conjunto de avaliação
(`evaluation_set/`) e documentação (`docs/`). O conjunto de avaliação fica na **raiz** e não dentro
de `tests/` deliberadamente: pelo Princípio IV ele é entregável de primeira classe, não fixture.

## Riscos ordenados por gravidade, com plano B

| # | Risco | Gravidade | Plano B |
|---|-------|-----------|---------|
| **R1** | **Consulta ao GKG estoura o orçamento de bytes** | Crítica | Dry run de 1 dia antes de tudo (V3). Cota diária no projeto impede o estouro por construção. Se a extrapolação passar de 200 GiB: reduzir colunas → reduzir baseline de 12 para 6 meses → amostrar dias, declarando na métrica |
| **R2** | **`maxrecords`=250 sem paginação impede enumerar menções** | Crítica | Já resolvido no desenho (D7): `TimelineVolRaw` conta, `ArtList` detalha, a diferença é medida e reportada. Exige reescrever FR-023 |
| **R3** | **Sandbox bloqueia DML e mata o dbt incremental** | Alta | Decisão D4: billing habilitado + 4 travas + alerta de orçamento. Se o autor recusar o cartão: todos os modelos viram `table`, e FR-030/FR-031 perdem o merge |
| **R4** | `gkg_partitioned` pode não estar mais atualizada | Alta | V1 antes de tudo. Plano B: `gkg` não particionada com filtro de `DATE` e janela reduzida |
| **R5** | Precisão < 85% nas marcas ambíguas | Alta | Camada 3 mais restritiva (proximidade menor + exclusões mais amplas) sobe precisão às custas de revocação. Reportar as duas. Camada 4 só entra se superar a linha de base |
| **R6** | Backfill de 3 meses ≈ 53 min estoura o SC-006 | Média | Já resolvido (D8): SLA vale para o ciclo diário; backfill é DAG separado. Exige ajustar SC-006 |
| **R7** | GKG não tem país da fonte; recorte Brasil fica sem base | Média | D9: cadastro de veículos brasileiros via `sourcecountry:brazil` da DOC API, custo zero de BigQuery |
| **R8** | Cota gratuita de API de modelo se esgota | Média | Fallback determinístico é obrigatório e é o que roda nos testes. A demo nunca depende do modelo |
| **R9** | SPA/MF sem arquivo estruturado | Baixa | D10: seed CSV transcrito, datado, 7 linhas. É SHOULD |
| **R10** | Prazo de 7 dias | Média | Ordem de corte já fixada na spec. Congelamento de ferramentas no dia 4, portão do COULD no dia 5 |

## Premissas assumidas

1. O autor tem conta Google e aceita habilitar billing com alerta em R$ 0,01 (decisão D4). Se
   recusar, o plano degrada para modelos `table` e perde o merge incremental.
2. Docker e Docker Compose disponíveis no notebook, com RAM suficiente para Airflow + Postgres +
   MongoDB + MinIO simultâneos.
3. A cobertura do GDELT para as 7 marcas é suficiente para produzir volume diário não trivial. Se
   uma marca tiver volume próximo de zero, isso é resultado legítimo e vira achado da apresentação,
   não defeito do pipeline.
4. Volume diário por marca fica abaixo de 250 artigos (V7 confirma). Caso contrário, o fatiamento
   por subjanela entra em ação.
5. O conjunto de avaliação será rotulado pelo próprio autor, com o critério de rotulagem escrito
   antes da rotulagem para evitar viés de confirmação.
6. Free tier de API de modelo disponível; se não, o fallback determinístico sustenta a entrega.

## Conflitos que exigem decisão do autor

Registrados aqui porque o enunciado manda parar e sinalizar quando algo conflita com a
constituição ou com a spec:

1. **FR-023** afirma coincidência exata entre menções listadas e volume da série. A API não
   permite. Proposta: reescrever para reconciliação medida e reportada.
2. **SC-006** afirma pipeline completo em < 20 min. Vale para o ciclo diário, não para o backfill.
   Proposta: separar os dois SLAs no texto.

Nenhum dos dois é corrigido unilateralmente neste plano — ambos alteram a spec, que é entregável
versionado.

## Complexity Tracking

| Violação aparente | Por que é necessária | Alternativa simples rejeitada porque |
|-------------------|---------------------|--------------------------------------|
| Quatro tecnologias de armazenamento (Mongo, MinIO, Postgres, BigQuery) | Cada uma resolve um problema distinto: esquema volátil do JSON cru, portabilidade S3 da zona colunar, metastore do Airflow, e warehouse analítico | Um só banco não cobre landing semiestruturada e warehouse colunar ao mesmo tempo sem perder o Princípio III ou o V |
| Duas fontes GDELT (API + BigQuery) | A DOC 2.0 tem janela confirmada de 3 meses e não alcança a linha de base de 12 meses exigida por SC-002 | Fonte única não atende SC-001 e SC-002 simultaneamente |
| Quatro camadas de identificação | Princípio IV exige precisão medida; nomes ambíguos não sobrevivem a match de string | Contagem por string produz o "número errado com aparência de certo" que a spec proíbe |
