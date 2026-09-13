# ADR 0001: Projeto BigQuery com billing habilitado em vez do Sandbox

**Data**: 2026-09-08
**Status**: aceita

## Contexto

O Princípio I exige custo zero com trava técnica. O **BigQuery Sandbox** seria a trava
perfeita: dispensa cartão de crédito e aplica os limites do free tier, de modo que a cobrança
é **tecnicamente impossível**.

Porém, a [documentação oficial](https://docs.cloud.google.com/bigquery/docs/sandbox) confirma
que o Sandbox **bloqueia statements DML** (INSERT, UPDATE, DELETE), bloqueia streaming inserts
e expira toda tabela, view e partição em **60 dias**, sem possibilidade de alterar a expiração.

A materialização `incremental` do dbt no BigQuery usa `MERGE`, que é DML. No Sandbox, os fatos
incrementais com merge exigidos por FR-030 e FR-031 simplesmente não rodam — e a História 5
(idempotência e reprocessamento) perde exatamente o conteúdo técnico que a torna defensável.

## Decisão

Usar projeto com **billing habilitado sobre o free tier** (1 TiB de query e 10 GiB de storage
por mês, permanentes), com **quatro travas cumulativas** em vez das três originalmente previstas.

## Alternativas descartadas

| Alternativa | Por que foi descartada |
|-------------|------------------------|
| **BigQuery Sandbox** | Bloqueia DML: mata `dbt incremental` e esvazia FR-030/FR-031. A segurança absoluta de custo sairia ao preço da capacidade central do projeto |
| Apenas `maximum_bytes_billed` | Trava por job é contornável por quem escreve a query. O Princípio I exige explicitamente que o teto seja configuração do projeto, "não escolha de quem escreve a query" |
| DuckDB local no lugar do BigQuery | Elimina o problema de custo, mas elimina junto a demonstração de disciplina de custo em warehouse cobrado por byte — que é justamente a habilidade em exibição |
| Sandbox + modelos `table` full refresh | Cabe no volume do projeto, mas torna o teste de idempotência trivial e sem valor demonstrativo |

## Consequências

As quatro travas passam a ser, em ordem de força:

1. **Cota `Query usage per day` no projeto GCP** — fora do código, deliberadamente. É a única
   que nenhum caminho de código consegue contornar.
2. `maximum_bytes_billed` por job, lido de config central e nunca de parâmetro de chamada.
3. Dry run obrigatório antes de toda execução, com bytes estimados em log. Dry run não é cobrado.
4. Validação programática de `_PARTITIONTIME` antes do envio — a consulta nem chega ao BigQuery.

Mais: alerta de orçamento em R$ 0,01 no billing, e orçamento auto-imposto de 200 GiB no projeto
inteiro (20% do free tier mensal, com 80% de folga para erro humano e reexecução).

**O que piora**: o risco de cobrança passa de zero absoluto para "quase zero, garantido por
quatro camadas". É uma piora real, assumida conscientemente. E exige cartão de crédito, o que é
uma barreira para quem for reproduzir o projeto — documentado no README.
