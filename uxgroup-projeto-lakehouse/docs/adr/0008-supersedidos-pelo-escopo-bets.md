# ADR 0008 — ADRs 0001 a 0005 superados pela mudança de escopo

**Status**: Aceito
**Data**: 2026-09-11

## Contexto

A constituição do projeto passou de 1.0.0 para 2.0.0 numa mudança **MAJOR**: o escopo deixou de
ser inteligência de menções de marca sobre uma fonte pública externa e passou a ser uma
plataforma analítica de apostas esportivas sobre dados sintéticos no Snowflake.

Os ADRs abaixo decidiam questões que não existem mais. Ficam registrados como histórico —
apagá-los removeria o raciocínio que levou até aqui, e o Princípio X trata documentação como
entregável.

| ADR | Decidia | Por que caiu |
|---|---|---|
| [0001](./0001-bigquery-billing-vs-sandbox.md) | Trava de bytes faturáveis no BigQuery | Não há BigQuery. O controle de custo agora é warehouse XSMALL com `AUTO_SUSPEND = 60` na conta trial do Snowflake |
| [0002](./0002-cliente-http-proprio.md) | Cliente HTTP próprio com backoff e cache | Não há fonte externa. Os dados são gerados localmente |
| [0003](./0003-cosmos-para-dbt-no-airflow.md) | astronomer-cosmos para orquestrar dbt | Superado especificamente pelo [ADR 0007](./0007-bashoperator-em-vez-de-cosmos.md) |
| [0004](./0004-duas-fontes-gdelt.md) | Uso de duas fontes do GDELT | Não há GDELT |
| [0005](./0005-mongodb-para-landing.md) | MongoDB como zona de aterrissagem | Não há zona de aterrissagem separada; RAW vive no Snowflake |

## Decisão

Os ADRs 0001, 0002, 0004 e 0005 estão **superados sem substituto** — a questão que resolviam
deixou de existir. O ADR 0003 está superado **com** substituto, o ADR 0007.

A especificação `specs/001-brand-mention-intelligence/` segue a mesma sorte e está marcada como
superada por `specs/002-betting-analytics-platform/`.

## Consequências

- Nenhum ADR de 0001 a 0005 deve ser citado como decisão vigente.
- As decisões técnicas em vigor estão em
  `specs/002-betting-analytics-platform/research.md` e nos ADRs 0006 e 0007.
