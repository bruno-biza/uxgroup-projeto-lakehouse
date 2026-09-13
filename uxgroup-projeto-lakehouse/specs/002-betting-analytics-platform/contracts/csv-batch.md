# Contrato — formato do lote na fronteira gerador → ingestão

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11

Esta é a única fronteira entre os dois módulos Python do projeto. Estava marcada como *Deferred* na
saída do `/speckit-clarify`; fica resolvida aqui.

## Layout de diretório e nomes

```text
<saida>/<YYYY-MM-DD>/
├── apostadores_<YYYY-MM-DD>.csv
├── eventos_<YYYY-MM-DD>.csv
├── apostas_<YYYY-MM-DD>.csv
└── transacoes_<YYYY-MM-DD>.csv
```

O nome carregar a data é o que dá ao `COPY INTO` um identificador estável e ao operador humano a
capacidade de olhar o stage e entender o que está lá. Os quatro arquivos são obrigatórios: um lote
incompleto é erro de ingestão, não lote vazio. Lote vazio legítimo é o arquivo presente com apenas
a linha de cabeçalho — caso de borda previsto na spec.

## Formato

| Propriedade | Valor | Por quê |
|---|---|---|
| Codificação | UTF-8 sem BOM | BOM aparece como lixo na primeira coluna do `COPY INTO` |
| Terminador de linha | `\n` explícito | `\r\n` em Windows mudaria o checksum entre plataformas ([D5](../research.md)) |
| Delimitador | `,` | — |
| Cabeçalho | obrigatório, uma linha | `SKIP_HEADER = 1` no file format |
| Quoting | somente quando necessário, `"` | reduz diferença espúria entre execuções |
| Datas | `YYYY-MM-DD` | ISO-8601, sem ambiguidade de locale |
| Timestamps | `YYYY-MM-DD HH:MM:SS` UTC | sem offset; tudo é UTC no pipeline ([D7](../research.md)) |
| Decimais | duas casas fixas, ponto como separador | formatação estável para checksum |
| Nulo | campo vazio (sem `NULL`, sem `\N`) | um único jeito de representar ausência |
| Ordenação das linhas | pela chave natural, ascendente | determinismo do checksum |
| Ordem das colunas | exatamente a das tabelas abaixo | `COPY INTO` por posição |

## Colunas por arquivo

**`apostadores_<data>.csv`**

```csv
apostador_id,criado_em,estado,atualizado_em
```

**`eventos_<data>.csv`**

```csv
evento_id,esporte,campeonato,time_casa,time_visitante,data_evento,atualizado_em
```

**`apostas_<data>.csv`**

```csv
aposta_id,apostador_id,evento_id,data_aposta,valor_apostado,odd,status,premio_pago,atualizado_em
```

**`transacoes_<data>.csv`**

```csv
transacao_id,apostador_id,data_transacao,tipo,valor,atualizado_em
```

## O que o gerador tem permissão de escrever

O ponto do contrato: **o CSV é o dado sujo**. Os defeitos injetados aparecem aqui, e a ingestão não
tem licença para corrigi-los.

- Campo obrigatório pode vir vazio (`nulo_obrigatorio`).
- `valor_apostado` pode vir `0.00` ou negativo (`valor_nao_positivo`).
- `data_aposta` pode ser posterior a `data_evento` do mesmo `evento_id`
  (`data_posterior_ao_evento`).
- O mesmo `aposta_id` pode aparecer em duas linhas com conteúdo divergente e `atualizado_em`
  diferente (`duplicata`) — o que quebra a ordenação por chave natural como critério único, então a
  ordenação de desempate é por `atualizado_em` e depois pelas colunas restantes em ordem fixa.
- `apostador_id` ou `evento_id` podem referenciar identificador inexistente no mesmo lote.

O que o gerador **nunca** escreve: coluna fora da ordem acima, arquivo sem cabeçalho, data em outro
formato, ou qualquer dado pessoal real.

## Consequência para a ingestão

Como todas as colunas de RAW são `VARCHAR` (ver [data-model.md](../data-model.md)), nenhum desses
defeitos faz o `COPY INTO` falhar. O file format usa `ON_ERROR = ABORT_STATEMENT`, e isso é
deliberado: com tipagem só em STAGING, um erro de `COPY INTO` passa a significar arquivo
corrompido — problema de infraestrutura — e não dado sujo, que é problema esperado e tratado pela
quarentena. A distinção é o que torna `ON_ERROR = ABORT_STATEMENT` seguro aqui em vez de frágil.
