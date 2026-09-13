# ADR 0005: MongoDB na landing zone dos JSON crus

**Data**: 2026-09-08
**Status**: aceita

## Contexto

O Princípio III (NÃO-NEGOCIÁVEL) exige que toda resposta seja persistida **como recebida, sem
parse**, antes de qualquer transformação.

A resposta da DOC 2.0 é JSON semiestruturado cujo formato varia por modo (`ArtList`,
`TimelineVolRaw`, `TimelineTone`) e pode mudar sem aviso: é uma API pública gratuita, sem
contrato de estabilidade nem versionamento formal.

## Decisão

MongoDB local em contêiner como landing zone dos JSON crus, com os metadados de captura ao lado
do corpo bruto.

## Alternativas descartadas

| Alternativa | Por que foi descartada |
|-------------|------------------------|
| PostgreSQL com coluna `JSONB` | Funcionaria, mas o Postgres já é metastore do Airflow. Misturar landing zone com metastore acopla dois ciclos de vida bem diferentes: um `docker compose down -v` para resetar o Airflow levaria junto o dado irrecuperável |
| Arquivos JSON soltos em disco | Sem índice por `request_hash`, a deduplicação de captura e o cache viram varredura de diretório |
| Gravar direto em Parquet | Parquet exige esquema. Definir esquema é parse, e parse antes da persistência viola o Princípio III |

## Consequências

- Esquema volátil absorvido sem migração: mudança de formato da API não quebra a ingestão.
- Índice único `(request_hash, logical_date)` entrega idempotência de captura de graça.
- **O que piora**: mais um serviço no Compose e mais RAM consumida no notebook.
- A zona colunar (Parquet em MinIO) continua existindo, mas para a extração do BigQuery — que
  **tem** esquema estável e por isso pode ser tipada na entrada.
