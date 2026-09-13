# ADR 0003: `astronomer-cosmos` em vez de `BashOperator`

**Data**: 2026-09-08
**Status**: aceita

## Contexto

O Princípio XI exige observabilidade, e o enunciado do projeto pede explicitamente que cada
modelo dbt apareça como tarefa observável no grafo do Airflow, não como comando opaco.

## Decisão

Usar [`astronomer-cosmos`](https://github.com/astronomer/astronomer-cosmos) com `DbtTaskGroup`,
que cria uma tarefa Airflow por modelo dbt e executa os testes logo após a materialização de
cada modelo.

## Alternativas descartadas

| Alternativa | Por que foi descartada |
|-------------|------------------------|
| `BashOperator` chamando `dbt build` | Produz **uma única caixa-preta** no grafo. Quando falha, o Airflow informa "a task dbt falhou" e nada mais: o modelo exato e a linhagem ficam invisíveis, e o retry reprocessa tudo |
| Um `BashOperator` por modelo, escrito à mão | Duplica em Python o grafo de dependências que o dbt já conhece. Toda mudança de modelo exigiria mudança no DAG — duas fontes de verdade divergindo |
| `dbt Cloud` | Custo. Viola o Princípio I |

## Consequências

- Falha de um modelo isola a tarefa correspondente; o retry é por modelo, não por pipeline.
- O grafo do Airflow passa a ser a linhagem, o que atende ao Princípio V de forma visível.
- **O que piora**: uma dependência a mais e acoplamento à forma como o Cosmos interpreta o
  `manifest.json` do dbt. Adicionada antes do congelamento de ferramentas do dia 4.
