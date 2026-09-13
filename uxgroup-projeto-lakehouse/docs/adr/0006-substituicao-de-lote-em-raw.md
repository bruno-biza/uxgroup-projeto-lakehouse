# ADR 0006 — Substituição de lote em RAW, e não apenas append

**Status**: Aceito
**Data**: 2026-09-11
**Contexto constitucional**: tensão com o Princípio III, resolvida aqui conforme exige a seção
Governance (emenda de interpretação registrada em ADR).

## Problema

O Princípio III diz que RAW é *append-only* e nunca editada. O Princípio IV e o critério `SC-002`
exigem que reprocessar o mesmo lote produza exatamente o mesmo estado final.

A proposta inicial era apoiar a idempotência da carga no histórico de carga do `COPY INTO`, que
ignora arquivos já carregados. Esse histórico identifica um arquivo pelo par **nome + ETag**.
Enquanto o conteúdo do arquivo não muda, funciona.

Mas o gerador é parametrizado por volume, semente e taxas de defeito, e regerar a mesma data com
outros parâmetros é exatamente o que se faz durante o desenvolvimento e durante a demonstração ao
vivo. Nesse caso o ETag muda, o `COPY INTO` carrega o arquivo de novo, e RAW passa a conter as
linhas das duas gerações. `SC-002` falharia de forma intermitente — o modo de falha mais caro de
diagnosticar, porque só aparece quando alguém regera um lote.

## Alternativas consideradas

**Confiar apenas no histórico de carga.** Rejeitada: não sobrevive à regeração do lote, como
acima. Também tem prazo de validade — o histórico expira em 64 dias.

**`TRUNCATE` da tabela RAW a cada execução.** Rejeitada: destrói os outros dias e inviabiliza o
cenário de `FR-019a`, em que um lote posterior traz a atualização de uma aposta antiga.

**Uma tabela RAW por data.** Rejeitada: multiplica objetos no warehouse sem ganho algum num
volume desta ordem, e complica todo `SELECT` a jusante.

## Decisão

A ingestão apaga as linhas da data lógica e recarrega, dentro de uma transação por tabela:

```sql
DELETE FROM raw_<entidade> WHERE lote_data = :data_lote;
-- PUT + COPY INTO ... FORCE = TRUE
```

A idempotência passa a ser propriedade do nosso código, não de um comportamento do warehouse que
não controlamos. O histórico de carga vira otimização, não garantia.

## Por que isto não viola o Princípio III

A leitura que este projeto adota — e que a especificação já registrava em `Assumptions` — é que
**o lote é a verdade completa do seu conteúdo bruto, e é substituído inteiro**.

Três fatos sustentam a compatibilidade:

1. **Nenhum `UPDATE` toca RAW.** Nenhuma linha é editada; a operação é remover o conjunto e
   repô-lo.
2. **O conteúdo continua sendo o CSV como veio.** Todas as colunas de negócio são `VARCHAR`, sem
   conversão, filtro ou deduplicação. A promessa central do Princípio III — preservar o dado
   irrecuperável como chegou — permanece intacta.
3. **A granularidade da imutabilidade é o lote, não a linha.** Um lote nunca é alterado
   parcialmente.

## Consequências

- A idempotência funciona mesmo quando o conteúdo do lote muda entre execuções.
- A janela de retenção de 64 dias do histórico de carga deixa de importar.
- Custo: cada recarga faz um `DELETE` a mais. Irrelevante no volume do projeto.
- Risco aceito: apagar o lote errado por passar a data lógica errada. Mitigado por a data ser
  sempre parâmetro explícito, nunca implícita (`FR-003`), e por a operação ser transacional.
