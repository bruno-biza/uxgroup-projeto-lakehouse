# ADR 0007 — BashOperator e virtualenv isolado, em vez de astronomer-cosmos

**Status**: Aceito — supersede o [ADR 0003](./0003-cosmos-para-dbt-no-airflow.md)
**Data**: 2026-09-11

## Problema

O dbt precisa ser executado pelo Airflow. Há duas formas usuais: um operador dedicado que lê o
grafo do dbt e o expande em tarefas do Airflow (astronomer-cosmos), ou uma chamada direta de
linha de comando.

Há ainda um problema anterior a essa escolha: **Airflow 2.9 e dbt-core não convivem bem no mesmo
interpretador**. O Airflow publica um arquivo de restrições que fixa versões de `jinja2`, `click`,
`packaging` e `urllib3`; o dbt-core exige faixas diferentes de várias delas. A resolução conjunta,
quando ocorre, produz um conjunto que quebra um dos lados em tempo de execução — tipicamente com
erro de Jinja de difícil diagnóstico.

## Decisão

1. dbt vive num **virtualenv isolado dentro da mesma imagem** do Airflow, em `/opt/dbt-venv`.
2. A DAG chama `/opt/dbt-venv/bin/dbt` por caminho absoluto, via `BashOperator`.
3. Uma tarefa por etapa: `dbt_run_staging`, `dbt_test_staging`, `dbt_run_marts`, `dbt_test_marts`.

## Alternativas consideradas

**astronomer-cosmos** (escolha do ADR 0003, agora superada). Dá granularidade por modelo na
interface do Airflow, o que é genuinamente útil em projeto grande. Rejeitada aqui por três
motivos: acrescenta uma dependência que também disputa versões com o Airflow; o ganho de
granularidade é pequeno num projeto de dez modelos; e o Princípio IX manda preferir o fluxo
simples que funciona ao arranjo sofisticado. Num prazo de três dias, cada dependência a mais é um
modo de falha a mais na véspera da apresentação.

**`DockerOperator` com imagem dbt separada.** Rejeitada por exigir o socket do Docker dentro do
contêiner do Airflow — mais partes móveis, e uma falha a mais possível no dia da demo.

**Instalar dbt ao lado do Airflow.** Rejeitada pelo conflito de restrições descrito acima, que é
conhecido e reprodutível.

## Consequências

- A interface do Airflow mostra seis tarefas, não um nó por modelo dbt. Para a demonstração isso
  é melhor: `dbt_test_staging` em vermelho comunica mais do que um nó interno qualquer.
- O portão de qualidade do Princípio V fica explícito e nomeado por camada.
- A imagem fica um pouco maior por carregar dois ambientes Python.
- Se o projeto crescer para dezenas de modelos, revisitar o cosmos passa a fazer sentido.
