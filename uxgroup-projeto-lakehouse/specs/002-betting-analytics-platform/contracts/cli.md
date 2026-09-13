# Contrato — CLIs de geração e ingestão

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11

As duas CLIs são a interface que o Airflow consome via `BashOperator`. O contrato aqui é o que a DAG
pode assumir; mudança em qualquer item abaixo é mudança de contrato e exige atualizar a DAG e o
README no mesmo PR (Princípio X).

Regras comuns às duas:

- Nenhuma delas lê data corrente. A data lógica é sempre argumento explícito (`FR-003`).
- Código de saída `0` em sucesso, diferente de zero em qualquer falha (`FR-018`).
- Log estruturado em stdout, uma linha por evento, com os campos obrigatórios da constituição.
- Credenciais só de variável de ambiente; nenhum argumento de linha de comando aceita segredo
  (Princípio VIII), para não vazar em `ps` nem no log do Airflow.

---

## `generator` — geração do lote sintético

```bash
python -m generator.cli \
  --data-lote 2026-09-10 \
  --volume 50000 \
  --saida /opt/dados/lotes \
  [--seed 42] \
  [--taxa-duplicadas 0.05] \
  [--taxa-nulos 0.03] \
  [--taxa-valor-invalido 0.02] \
  [--taxa-data-posterior 0.02]
```

| Argumento | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `--data-lote` | sim | — | Data lógica do lote, `YYYY-MM-DD`. Define `lote_data` e o nome dos arquivos |
| `--volume` | sim | — | Número de apostas do lote. As outras entidades são dimensionadas proporcionalmente |
| `--saida` | sim | — | Diretório raiz; os arquivos vão para `<saida>/<data-lote>/` |
| `--seed` | não | `42` | Semente única propagada para todos os geradores aleatórios |
| `--taxa-duplicadas` | não | `0.05` | Fração de apostas reemitidas como duplicata divergente |
| `--taxa-nulos` | não | `0.03` | Fração de registros com nulo em campo obrigatório |
| `--taxa-valor-invalido` | não | `0.02` | Fração de apostas com `valor_apostado` zero ou negativo |
| `--taxa-data-posterior` | não | `0.02` | Fração de apostas com `data_aposta > data_evento` |

**Garantias**:

1. Mesma `--seed`, mesma `--data-lote` e mesmo `--volume` produzem arquivos byte a byte idênticos —
   verificável por checksum (`SC-002`, Princípio VI).
2. As taxas são respeitadas com tolerância de arredondamento de uma linha por defeito, e a contagem
   efetiva de cada defeito é emitida no log para conferência contra `agg_qualidade_lote`.
3. Um defeito por registro. Registros que acumulam violações existem, mas por sobreposição
   estatística, não por construção — e o pipeline os conta uma vez só.
4. Nenhum campo contém dado pessoal real (Princípio VI).

**Saída no stdout** (última linha, JSON):

```json
{"evento":"lote_gerado","lote_data":"2026-09-10","seed":42,
 "linhas":{"apostadores":5000,"eventos":800,"apostas":50000,"transacoes":12000},
 "defeitos":{"duplicata":2500,"nulo_obrigatorio":1500,"valor_nao_positivo":1000,
             "data_posterior_ao_evento":1000},
 "checksums":{"apostas_2026-09-10.csv":"sha256:..."},"duracao_s":12.4}
```

**Falhas**: taxa fora de `[0, 1]`, soma das taxas acima de `1.0`, data em formato inválido,
diretório de saída não gravável. Todas com mensagem em stderr e código diferente de zero.

---

## `ingestion` — carga da camada RAW

```bash
python -m ingestion.cli \
  --data-lote 2026-09-10 \
  --diretorio /opt/dados/lotes
```

| Argumento | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `--data-lote` | sim | — | Data lógica; seleciona `<diretorio>/<data-lote>/` e o valor de `lote_data` |
| `--diretorio` | sim | — | Diretório raiz dos lotes, o mesmo passado em `--saida` ao gerador |

**Variáveis de ambiente exigidas** — ausência de qualquer uma é erro antes de qualquer conexão:

`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA_RAW`.

**Sequência por entidade**:

1. `DELETE FROM raw_<entidade> WHERE lote_data = :data_lote` — substituição por lote
   ([D1](../research.md#d1)).
2. `PUT file://... @STG_LOTES/<data_lote>/ OVERWRITE = TRUE`.
3. `COPY INTO raw_<entidade> ... FORCE = TRUE` com `METADATA$FILENAME` e
   `METADATA$FILE_ROW_NUMBER` nas colunas de metadados.

As três etapas de cada entidade ocorrem na mesma transação: falha no `COPY INTO` não deixa a tabela
sem as linhas que o `DELETE` removeu.

**Garantias**:

1. Executar duas vezes com a mesma `--data-lote` deixa RAW no mesmo estado, com a mesma contagem de
   linhas (`FR-019`, `SC-002`) — independentemente de o conteúdo do arquivo ter mudado entre as
   execuções.
2. Nenhuma conversão de tipo, filtro ou renomeação é aplicada (`FR-004`, Princípio III).
3. Um lote de outra data nunca é afetado.

**Saída no stdout** (última linha, JSON):

```json
{"evento":"raw_carregada","lote_data":"2026-09-10",
 "linhas_por_tabela":{"raw_apostadores":5000,"raw_eventos":800,
                      "raw_apostas":52500,"raw_transacoes":12000},
 "linhas_removidas_antes":0,"duracao_s":31.7}
```

`raw_apostas` recebe mais linhas que `--volume` porque as duplicatas injetadas são linhas
adicionais — é em STAGING que elas são resolvidas.

**Falhas**: variável de ambiente ausente, diretório do lote inexistente ou incompleto, erro de
autenticação, `COPY INTO` com arquivo ilegível. Todas abortam antes de deixar estado parcial.
