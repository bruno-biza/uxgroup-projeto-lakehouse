# Phase 1 — Modelo de Dados

**Feature**: 001-brand-mention-intelligence | **Date**: 2026-09-08

Regra estrutural (Princípio V): cada camada lê **apenas** da imediatamente anterior. Salto é
proibido e detectável na linhagem gerada pelo Cosmos/dbt docs.

```
landing (Mongo + MinIO)  →  bronze (BQ)  →  silver (BQ)  →  gold (BQ, estrela)
   imutável, sem parse       tipado,          menções             marts
                             deduplicado      desambiguadas
```

---

## Camada landing — imutável

### `mongo.landing.gdelt_doc_responses`

Resposta da DOC 2.0 gravada **byte a byte, antes de qualquer parse** (Princípio III).

| Campo | Tipo | Nota |
|-------|------|------|
| `_id` | ObjectId | |
| `request_hash` | string | SHA-256 da URL canônica — chave do cache (Princípio II) |
| `url` | string | URL completa da requisição |
| `params` | object | `query`, `mode`, `format`, `startdatetime`, `enddatetime`, `maxrecords` |
| `mode` | string | `ArtList` \| `TimelineVolRaw` \| `TimelineTone` |
| `logical_date` | date | Data lógica vinda do orquestrador — nunca data corrente (Princípio IX) |
| `captured_at` | timestamp | Momento da captura |
| `http_status` | int | |
| `attempts` | int | Tentativas até sucesso |
| `duration_ms` | int | |
| `raw_body` | string | **Corpo cru, sem parse** |
| `truncated_at_max` | bool | `true` se `ArtList` devolveu exatamente 250 → dispara fatiamento |

Índice único: `(request_hash, logical_date)` — garante idempotência da captura.

### `minio://landing/gkg/dt=YYYY-MM-DD/*.parquet`

Extração única do GKG (Princípio I, regra de extração única). Imutável, append-only. Colunas
mínimas, confirmadas em V2 antes do código:

`gkg_record_id`, `date`, `document_identifier`, `source_common_name`, `v2_themes`, `v2_tone`,
`extraction_metadata` (bytes estimados, bytes faturados, id do job, `_PARTITIONTIME` consultado).

---

## Camada bronze — tipado e deduplicado

| Modelo | Materialização | Chave | Regra |
|--------|---------------|-------|-------|
| `stg_gdelt_articles` | view | `article_url` | Parse do `raw_body` do ArtList: `url`, `title`, `domain`, `language`, `sourcecountry`, `seendate` |
| `stg_gdelt_timeline_volume` | view | `(query_id, date)` | Contagem bruta por dia — numerador e denominador |
| `stg_gdelt_timeline_tone` | view | `(query_id, date)` | Tom médio por dia |
| `stg_gkg_documents` | view | `gkg_record_id` | 1:1 com o Parquet, tipagem e renomeação |
| `br_articles` | incremental, merge | `article_url` | Deduplicação de captura: mesma URL capturada N vezes = 1 linha (FR-031) |

**Regra de deduplicação (FR-031), documentada e testada**: a chave de negócio é
`(veiculo_dominio, conteudo_hash)`. O mesmo texto republicado por 40 portais gera **40 menções, uma
por veículo**. O mesmo texto capturado 2× do mesmo portal gera **1 menção**.

---

## Camada silver — menções desambiguadas

### `sl_brand_mentions`

O coração do projeto. Uma linha por (conteúdo, marca identificada).

| Campo | Tipo | Origem / regra |
|-------|------|----------------|
| `mention_id` | string | Hash de `(article_url, brand_id)` |
| `brand_id` | string | FK → `dim_brand` |
| `article_url` | string | FK → conteúdo |
| `published_at` | timestamp | |
| `logical_date` | date | Do orquestrador |
| `outlet_domain` | string | FK → `dim_outlet` |
| `source_country` | string | FK → `dim_country` |
| `source_language` | string | FK → `dim_language` |
| `title` | string | |
| `tone_indicator` | float | Sinal automatizado da fonte — **nunca** rotulado como sentimento (FR-021) |
| `identification_layer` | int | **1** domínio, **2** nome único, **3** ambíguo com contexto, **4** IA |
| `identification_method` | string | Descrição legível do sinal que decidiu |
| `confidence` | float | 0–1 |
| `above_confidence_floor` | bool | Comparação com o piso vigente (FR-004a) |
| `confidence_floor_version` | string | Versão do piso na hora do cálculo (FR-004b) |

**Regra crítica (FR-004c)**: linhas com `above_confidence_floor = false` **permanecem na tabela** e
são consultáveis, mas são excluídas de toda métrica de negócio. Nada é apagado.

### `sl_category_coverage`

Denominador do share of voice (FR-013).

| Campo | Tipo | Nota |
|-------|------|------|
| `content_id` | string | |
| `date` | date | |
| `source_country` | string | Habilita o recorte Brasil (FR-020) |
| `inclusion_origin` | enum | `taxonomy` \| `term_list` \| `both` — exigido por FR-013 |
| `term_list_version` | string | Versão vigente da lista (FR-013a) |

### `sl_brand_baseline`

Linha de base de 12 meses por marca (FR-017), do GKG.

| Campo | Tipo | Nota |
|-------|------|------|
| `brand_id` | string | |
| `weekday` | int | Sazonalidade semanal |
| `median_volume` | float | Mediana da própria marca |
| `mad` | float | Desvio absoluto mediano (FR-027) |
| `mad_is_zero` | bool | Dispara a regra de dispersão nula (FR-027b) |
| `baseline_window` | string | Janela que produziu os parâmetros |

---

## Camada gold — esquema estrela

### Fato

**`fct_brand_mentions_daily`** — grão: `(brand_id, date_key, outlet_key)`.
Incremental com merge sobre chave única (Princípio IX).

Medidas: `mention_count`, `mentions_below_floor` (FR-004d), `avg_tone`,
`sov_global`, `sov_brasil` (FR-020 — **duas métricas nomeadas, nunca uma genérica**),
`denominator_global`, `denominator_brasil`.

### Dimensões (materialização `table`)

| Dimensão | Chave | Atributos |
|----------|-------|-----------|
| `dim_brand` | `brand_id` | `name`, `canonical_domain` (.bet.br), `known_variants[]`, `role` (própria/concorrente), `legal_name`, `cnpj`, `spa_authorization`, `ambiguity_risk` (alto/médio/baixo), `monitored_since` |
| `dim_outlet` | `outlet_key` | `domain`, `name`, `country`, `covers_category` (bool — habilita o espaço em branco, FR-019) |
| `dim_date` | `date_key` | `date`, `weekday`, `week`, `month` |
| `dim_language` | `language_key` | Código e nome |
| `dim_country` | `country_key` | Código e nome |

### Marts derivados

| Modelo | Atende | Nota |
|--------|--------|------|
| `mrt_share_of_voice_daily` | US2 | Duas séries nomeadas + volume absoluto que sustenta o recorte Brasil (FR-020b) |
| `mrt_mentions_detail` | US3 | Drill-down do dia + coluna de reconciliação ArtList × TimelineVolRaw |
| `mrt_outlet_distribution` | US4 | Fecha com o volume absoluto (FR-018) |
| `mrt_media_whitespace` | US8 | Anti-join `dim_outlet.covers_category` × menções de marca própria, com limiar (FR-038) |
| `mrt_anomalies` | US10/US11 | Desvio em MAD, N e janela vigentes, hipótese rotulada não verificada, status de revisão |

---

## Entidades fora do fluxo de camadas

### `evaluation_set/labeled_mentions.csv` — versionado no Git

| Campo | Nota |
|-------|------|
| `candidate_id`, `article_url`, `title`, `outlet_domain`, `brand_candidate` | |
| `human_label` | `marca` \| `nao_marca` |
| `label_reason` | Por que — força o rotulador a explicitar o critério |
| `labeled_by`, `labeled_at` | |
| `ambiguity_case` | `reals_moeda`, `reals_clube`, `bingo_jogo`, `esportiva_expressao`, `esportiva_veiculo`, `betgo_generico`, `kto_sigla`, `nenhum` |

Amostragem **estratificada**: ≥ 300 linhas com cobertura obrigatória de Reals, Bingo e Esportiva
(SC-004). Os estratos `ambiguity_case` garantem que os casos difíceis não sumam na amostra
aleatória — é a diferença entre medir precisão e medir sorte.

### `identification_metrics` (Postgres, serving)

`identifier_version`, `brand_id` (ou `_agregado_`), `layer` (1–4 ou `_todas_`), `precision`,
`recall`, `f1`, `measured_at`, `evaluation_set_version`.

**Teste de regressão (Princípio IV)**: compara com a versão anterior e **reprova a suíte** se a
precisão cair em qualquer marca.

### `ai_cache` (Mongo)

`prompt_version`, `input_hash`, `output`, `schema_valid`, `created_at`, `used_fallback`.
Determinístico por entrada; `used_fallback = true` é o que a suíte de testes exercita.

---

## Validações que viram teste dbt

| Regra | Modelo | Tipo |
|-------|--------|------|
| Unicidade e not-null da chave | todos | nativo |
| Integridade referencial | fatos → dimensões | `relationships` |
| Dedup: mesma URL 1×; mesmo texto = 1 por veículo | `br_articles` | singular |
| `sov` ∈ [0,1] e denominador > 0 | `fct_brand_mentions_daily` | `dbt_expectations` |
| Denominador zero → SoV **indefinido**, nunca zero | `mrt_share_of_voice_daily` | singular |
| Toda menção contada tem `above_confidence_floor = true` | `sl_brand_mentions` | singular |
| Toda menção tem `identification_layer` ∈ {1,2,3,4} | `sl_brand_mentions` | `accepted_values` |
| Dupla execução com mesma data lógica não altera contagem | `fct_brand_mentions_daily` | singular |
| Freshness com SLA da documentação da fonte | fontes | `source freshness` — `TODO(SLA_FRESHNESS)` |
| Toda coluna de mart tem `description` preenchida | todos | `dbt-checkpoint` |

Última linha não é burocracia: pelo Princípio VII as ressalvas metodológicas moram no
`description` da coluna, e é de lá que o dbt docs as publica.
