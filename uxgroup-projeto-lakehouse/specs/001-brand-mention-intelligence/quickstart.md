# Quickstart — Validação de ponta a ponta

**Meta**: um avaliador externo sobe o projeto e valida os critérios de sucesso em **menos de 30
minutos**, seguindo apenas este arquivo e o README (SC-011).

## Pré-requisitos

- Docker e Docker Compose
- Python 3.11
- Conta Google com projeto BigQuery **e cota diária de bytes configurada** (ver Passo 0)
- Nenhuma credencial vem no repositório — copie `.env.example` para `.env` e preencha

## Passo 0 — Verificações bloqueantes (antes de qualquer código rodar)

Nenhuma etapa seguinte começa antes destas passarem. Detalhes em
[research.md §9](./research.md).

```bash
make verify-sources
```

Este alvo executa, nesta ordem, e **falha na primeira que não passar**:

| # | Verifica | Custo |
|---|----------|-------|
| V1 | `MAX(_PARTITIONTIME)` de `gkg_partitioned` — a tabela ainda é atualizada? | zero (metadado) |
| V2 | Esquema real da tabela, nomes das colunas | zero |
| V3 | **Dry run de 1 dia** → extrapola × 365 → compara com o orçamento de 200 GiB | zero (dry run não é cobrado) |
| V4 | Cota diária de query configurada no projeto GCP | zero |
| V5 | `maximum_bytes_billed` faz uma query grande **falhar** em vez de cobrar | zero (falha antes de executar) |
| V6 | DOC 2.0 responde nos modos previstos; salva fixtures | 3 requisições |
| V7 | Volume diário da marca de maior volume < 250 no `ArtList` | 1 requisição |

O relatório fica em `docs/source_verification.md`. **Se V3 indicar estouro do orçamento, pare** e
aplique o plano B (reduzir colunas → 6 meses → amostrar dias) antes de seguir.

## Passo 1 — Subir o ambiente

```bash
make up
```

Sobe Airflow, PostgreSQL, MongoDB e MinIO. Airflow em `http://localhost:8080`.

```bash
make status   # todos os serviços saudáveis
```

## Passo 2 — Suíte de testes offline

```bash
make test
```

Roda **sem rede**. Prova três coisas de uma vez:

- Reconstrução completa a partir da zona bruta sem nenhuma chamada externa (SC-008)
- Query sem `_PARTITIONTIME` ou sem teto de bytes é rejeitada **antes do envio** (SC-009)
- Componentes de IA rodam inteiramente em modo fallback determinístico

## Passo 3 — Backfill histórico (uma vez, DAG separado)

```bash
make backfill
```

DAG `historical_backfill` — deliberadamente separado do ciclo diário para que **nunca rode por
acidente**. Faz a extração única do GKG com as quatro travas ativas e materializa em MinIO.

Ao final, `docs/cost_report.md` traz bytes estimados × bytes faturados por consulta. Se divergirem
muito, a estimativa do dry run está mal calibrada e é isso que você investiga.

**Expectativa**: ≥ 10 M linhas na camada bruta (SC-003), consumo total dentro dos 200 GiB.

## Passo 4 — Ciclo diário

```bash
make run DATE=2026-09-01
```

DAG `daily_mentions`, com data lógica **explícita** — nunca data corrente (Princípio IX).

Sequência: coletar → aterrissar cru → bronze → identificar marca por camadas → `dbt build` →
avaliar precisão → detectar anomalias → explicar anomalias → validar freshness → publicar docs.

**Expectativa**: conclusão em < 20 min (SC-006, ciclo diário — ver ressalva R2/R6 no plano).

## Passo 5 — Idempotência

```bash
make run DATE=2026-09-01    # de novo, mesma data
make check-idempotency DATE=2026-09-01
```

Compara contagem de linhas e checksum das camadas de consumo entre as duas execuções.
**Devem ser idênticos** (SC-010, História 5).

## Passo 6 — O entregável central

```bash
make eval
```

Gera `docs/evaluation_report.md`: precisão, revocação e F1 **por marca e por camada**, contra o
conjunto rotulado versionado.

**Expectativa**: ≥ 85% de precisão para Reals, Bingo, Esportiva, BetGO e KTO (SC-005), sem
regressão frente à versão anterior.

Este é o artefato que a apresentação defende. Se ele não existir, nenhuma métrica de negócio pode
ser publicada (Princípio IV, FR-007).

## Passo 7 — Documentação e linhagem

```bash
make docs
```

Publica o dbt docs com a linhagem gerada do código. Confira que:

- Cada modelo dbt aparece como **tarefa própria** no grafo do Airflow, não como comando opaco
- Nenhuma aresta pula uma camada (Princípio V)
- Toda coluna de mart tem `description`, e as ressalvas metodológicas estão lá (Princípio VII)
- A hipótese de anomalia **não tem aresta de saída** para nenhum fato

## Mapa: comando → critério de sucesso

| Critério | Comando | Onde ver |
|----------|---------|----------|
| SC-003 ≥ 10M linhas | `make backfill` | `docs/cost_report.md` |
| SC-005 precisão ≥ 85% | `make eval` | `docs/evaluation_report.md` |
| SC-006 ciclo < 20 min | `make run` | Airflow UI |
| SC-007 100% dos marts testados | `make test` | dbt test |
| SC-008 offline | `make test` | pytest `tests/offline/` |
| SC-009 travas de custo | `make test` | pytest `tests/unit/test_bigquery_guard.py` |
| SC-010 idempotência | `make check-idempotency` | Saída do comando |
| SC-011 setup < 30 min | Este arquivo | Cronômetro |
| SC-012 demo em 10 min | `docs/demo_script.md` | Cronômetro |
| SC-013/SC-014 ressalvas e descarte | `make docs` | dbt docs |
| SC-016 anomalia sintética | `make test` | pytest `tests/unit/test_anomaly.py` |

## Encerrar

```bash
make down          # para os serviços
make clean         # remove volumes — apaga a zona bruta, exige reexecutar o backfill
```
