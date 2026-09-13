# Contrato — GKG particionado no BigQuery

**Tabela**: `gdelt-bq.gdeltv2.gkg_partitioned` (nome **CONFIRMADO** —
[fonte](https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/))
**Pseudo-coluna de partição**: `_PARTITIONTIME` (**CONFIRMADA**)

Este contrato é a implementação do Princípio I. Nenhuma consulta à origem pública existe fora dele.

## Interface obrigatória — ponto único de acesso

```python
class BigQueryGuard:
    """Único caminho para a origem pública. Nenhum outro módulo importa o cliente BQ.

    Sem ponto único de acesso as três travas do Princípio I não são auditáveis:
    bastaria um caminho de código alternativo para furar todas.
    """

    def run(self, sql: str, logical_date: date) -> QueryResult:
        self._assert_partition_filter(sql)   # trava (c) — nem chega ao BigQuery
        est = self._dry_run(sql)             # trava (a) — dry run não é cobrado
        log.info("bq_dry_run", bytes_estimated=est, logical_date=logical_date)
        self._assert_within_budget(est)      # orçamento de 200 GiB do projeto
        return self._execute(sql, maximum_bytes_billed=CONFIG.max_bytes)  # trava (b)
```

## As quatro travas cumulativas

| # | Trava | Onde vive | Como é testada |
|---|-------|-----------|----------------|
| **1** | Cota `Query usage per day` no projeto GCP | Painel de quotas — **fora do código** | Verificação V4; nenhuma query a contorna |
| **2** | `maximum_bytes_billed` por job | `CONFIG.max_bytes`, config central | Query grande com teto baixo deve **falhar**, não cobrar (V5) |
| **3** | Dry run antes de toda execução | `BigQueryGuard._dry_run` | Teste afirma que `_execute` nunca é chamado sem `_dry_run` antes |
| **4** | Filtro de partição validado antes do envio | `_assert_partition_filter` | Teste: SQL sem `_PARTITIONTIME` levanta exceção **antes** de qualquer chamada de rede |

A trava 1 é a mais importante e é a que atende literalmente ao texto do Princípio I — "o teto é
configuração do projeto, não escolha de quem escreve a query".

## Sintaxe obrigatória do filtro (confirmada)

```sql
SELECT DATE, DocumentIdentifier, V2SourceCommonName, V2Tone
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP("2025-09-01")
  AND _PARTITIONTIME <  TIMESTAMP("2025-09-02")
```

Proibido: `SELECT *`; ausência de `_PARTITIONTIME`; qualquer consulta fora do `BigQueryGuard`.

## Regra de extração única (Princípio I)

A origem é consultada **uma vez por partição**, o resultado vai imediatamente para
`minio://landing/gkg/dt=YYYY-MM-DD/*.parquet`, e **toda** iteração posterior lê o Parquet. Reconsultar
a origem para iterar análise é violação, não otimização pendente.

## Verificações bloqueantes antes do código

| # | O quê | Comando | Se falhar |
|---|-------|---------|-----------|
| V1 | Tabela ainda atualizada | `SELECT MAX(_PARTITIONTIME) FROM ...` (metadado, custo zero) | `gkg` não particionada com filtro de `DATE`, janela reduzida, ADR |
| V2 | Nomes reais das colunas | `bq show --schema gdelt-bq:gdeltv2.gkg_partitioned` | Ajustar staging |
| V3 | **Bytes de 1 dia** | `bq query --dry_run` com as 4 colunas | Reduzir colunas → 6 meses → amostrar dias |

**V3 é o número mais importante do projeto.** Extrapolar × 365 e comparar com o orçamento de
200 GiB **antes** de tentar a janela cheia. Referência da própria fonte: uma consulta que varria
423 GB na tabela não particionada varreu 15 GB na particionada.

## Lacuna conhecida — país do veículo

O GKG **não** tem coluna de país da fonte, apenas `V2SourceCommonName` (domínio). O recorte
`share_of_voice_brasil` (FR-020) depende de mapear domínio → país. Decisão D9: construir
`dim_outlet` com `sourcecountry:brazil` da DOC API, que usa a classificação do próprio GDELT e
custa zero byte de BigQuery.
