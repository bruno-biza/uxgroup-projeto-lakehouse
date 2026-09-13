# Arquitetura

## Visão geral

```text
   ┌────────────────────────────── Airflow (local, Docker) ───────────────────────────────┐
   │                                                                                       │
   │  gerar_lote → carregar_raw → dbt_run_staging → dbt_test_staging → dbt_run_marts →     │
   │                                                                   dbt_test_marts      │
   └───────┬──────────────┬────────────────────────────┬───────────────────────────────────┘
           │              │                            │
           ▼              ▼                            ▼
   ┌──────────────┐  ┌──────────────┐        ┌────────────────────────────────────────┐
   │ generator/   │  │ ingestion/   │        │            dbt (Snowflake)             │
   │              │  │              │        │                                        │
   │ Faker + seed │  │ DELETE lote  │        │  RAW ──► STAGING ──► MARTS             │
   │ fixa         │  │ PUT stage    │        │                                        │
   │ 4 defeitos   │  │ COPY INTO    │        │  Cada camada lê só a anterior          │
   │ injetados    │  │ FORCE=TRUE   │        │                                        │
   └──────┬───────┘  └──────┬───────┘        └────────────────────────────────────────┘
          │ CSV/dia         │ VARCHAR puro
          └─────────────────┘
```

Único serviço remoto: a conta trial do Snowflake. Todo o resto roda local e open-source.

## Linhagem

O grafo abaixo corresponde ao que `dbt docs generate` produz a partir do código; ele não é
desenhado à mão e não deve divergir. Modelos `int_*` são efêmeros — existem como CTE embutido e
não criam objeto no warehouse.

```text
RAW.raw_apostadores ─┐
                     ├─► int_apostadores_validados ─┬─► stg_apostadores ──────────► dim_apostadores
                     │                              └─► stg_apostadores_rejeitadas ─┐
RAW.raw_eventos ─────┤                                                              │
                     ├─► int_eventos_validados ─────┬─► stg_eventos ──────────────► dim_eventos
                     │                              └─► stg_eventos_rejeitadas ─────┤
RAW.raw_apostas ─────┤                                                              │
                     ├─► int_apostas_validadas ─────┬─► stg_apostas ─► fct_apostas ─┼─► agg_ggr_diario_esporte
                     │        ▲        ▲            └─► stg_apostas_rejeitadas ─────┤   agg_engajamento_diario
                     │        │        │                                            │
RAW.raw_transacoes ──┤   stg_eventos  stg_apostadores                               │
                     └─► int_transacoes_validadas ──┬─► stg_transacoes ─► fct_transacoes ─► agg_financeiro_diario
                                                    └─► stg_transacoes_rejeitadas ──┤
                                                                                    ▼
                                                              qua_registros_rejeitados ─► agg_qualidade_lote
```

Note as duas arestas que sobem de `stg_eventos` e `stg_apostadores` para
`int_apostas_validadas`: a integridade referencial é avaliada contra a camada **limpa**, não
contra RAW. Uma aposta que referencia um apostador rejeitado também é inválida — aceitá-la
produziria métrica apoiada num cadastro que o próprio pipeline recusou.

## As três camadas

### RAW — o dado como chegou

Todas as colunas de negócio são `VARCHAR`, sem exceção. Sem conversão de tipo, não existe
conversão que falhe: uma aposta com valor negativo ou data impossível chega intacta à quarentena
em vez de derrubar a carga.

Consequência deliberada: um erro de `COPY INTO` significa **arquivo corrompido** — problema de
infraestrutura — e nunca dado sujo, que é problema esperado. É por isso que
`ON_ERROR = ABORT_STATEMENT` é seguro aqui, e não frágil.

Quatro colunas de metadados em todas as tabelas: `arquivo_origem`, `linha_origem`, `carregado_em`
e `lote_data`. As duas primeiras são o caminho de volta até a linha do CSV.

### STAGING — limpo, tipado, e o que sobrou

Cada entidade produz **dois** modelos: o limpo e a quarentena. A regra de validação é escrita uma
única vez, num modelo efêmero `int_*`, e consumida pelos dois — duplicá-la seria o caminho mais
curto para os dois divergirem e o invariante `recebidos = aceitos + rejeitados` parar de fechar.

A deduplicação usa `ROW_NUMBER()` particionado pela chave natural, ordenado pelo marcador de
atualização mais recente, com desempate final por `arquivo_origem` e `linha_origem`. Esse
desempate final é o que garante **ordem total**: sem ele, dois registros idênticos deixariam a
escolha indefinida e a reprodutibilidade falharia de forma intermitente.

A mesma ordenação vale dentro e entre lotes — "vence o mais recente" é uma regra só.

### MARTS — métricas de negócio

Fatos incrementais com `merge` por identificador; agregados reconstruídos por inteiro a cada
execução.

Essa combinação não é arbitrária. É o que faz uma aposta que sai de `pendente` num lote posterior
recalcular automaticamente o GGR da **data original** dela, sem uma linha de código de backfill.
Num volume de dezenas de milhares de linhas, reconstruir quatro agregações custa segundos.

## Idempotência

Três mecanismos em camadas diferentes:

1. **RAW**: a ingestão apaga as linhas da data lógica e recarrega com `FORCE = TRUE`, numa
   transação por tabela. Não depende do histórico de carga do `COPY INTO`, que só reconhece o par
   nome + ETag e recarregaria um lote regerado com outros parâmetros. Ver
   [ADR 0006](adr/0006-substituicao-de-lote-em-raw.md).
2. **Fatos**: `merge` por chave única. Reexecutar substitui, nunca acrescenta.
3. **Agregados**: reconstruídos do zero, então são função pura do estado dos fatos.

A data lógica vem sempre do `{{ ds }}` do Airflow, nunca do relógio. Um teste varre a árvore
sintática dos módulos Python e reprova qualquer `datetime.now()` ou `date.today()` em código de
pipeline.

## Portão de qualidade

`dbt_test_staging` e `dbt_test_marts` são tarefas próprias da DAG. Falha em qualquer uma aborta a
execução, e a tarefa seguinte não roda — MARTS permanece exibindo os números do lote anterior,
coerentes entre si.

O que **não** bloqueia: a taxa de rejeição, por maior que seja. Os defeitos são injetados de
propósito; uma taxa alta é comportamento esperado, não anomalia. A taxa é reportada em
`agg_qualidade_lote`.

## Controle de custo

O warehouse é `XSMALL` com `AUTO_SUSPEND = 60` e `INITIALLY_SUSPENDED = TRUE`, declarados em
`snowflake_setup/01_warehouse.sql`. Ele se suspende sozinho após um minuto de inatividade — não há
ação manual para parar de consumir crédito, e o setup em si não gasta.

Tudo o que não é o warehouse roda local: Airflow, Postgres, dbt e o gerador.

## Segredos

Nenhuma credencial no código ou no histórico. As sete variáveis do Snowflake vêm do ambiente; o
`.env` está no `.gitignore` e o `.env.example` documenta as chaves sem valores. O `profiles.yml`
do dbt usa `env_var()` sem default — um default silencioso conectaria no lugar errado.

`ConfigSnowflake.__repr__` oculta a senha, para que um traceback não a vaze no log do Airflow.

## Limitação conhecida

dbt garante atomicidade **por modelo**, não por execução. Se um teste reprovar entre a construção
dos fatos e a dos agregados, `fct_apostas` pode ficar momentaneamente à frente dos `agg_*`. A
alternativa realmente atômica — construir num schema paralelo e usar `ALTER SCHEMA ... SWAP WITH`
— foi rejeitada porque quebra o estado dos modelos incrementais. O raciocínio completo está em
`specs/002-betting-analytics-platform/research.md`, decisão D3.
