# Registros de Decisão de Arquitetura

Pelo Princípio X, decisão relevante vira ADR — **e ferramenta avaliada e descartada também**.
O valor de portfólio de um ADR está tanto no que foi escolhido quanto no que foi recusado e
por quê: a segunda coluna da tabela "Alternativas descartadas" é a que mostra julgamento.

| # | Decisão | Status |
|---|---------|--------|
| [0001](0001-bigquery-billing-vs-sandbox.md) | Projeto com billing em vez do BigQuery Sandbox | aceita |
| [0002](0002-cliente-http-proprio.md) | Cliente HTTP próprio em vez do pacote `gdeltdoc` | aceita |
| [0003](0003-cosmos-para-dbt-no-airflow.md) | `astronomer-cosmos` em vez de `BashOperator` | aceita |
| [0004](0004-duas-fontes-gdelt.md) | Duas fontes GDELT complementares | aceita |
| [0005](0005-mongodb-para-landing.md) | MongoDB na landing zone | aceita |
| 0006 | SLA de freshness — pendente, ver `TODO(SLA_FRESHNESS)` | proposta |

## Template

Ver [template.md](template.md). Um ADR tem quatro seções: contexto (fatos, não preferências),
decisão (uma frase imperativa), alternativas descartadas com o motivo, e consequências —
**incluindo o que piora**. ADR que só lista vantagens não é decisão, é propaganda.
