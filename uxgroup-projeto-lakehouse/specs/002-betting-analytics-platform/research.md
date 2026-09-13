# Phase 0 — Research: Plataforma Analítica de Apostas Esportivas

**Feature**: `002-betting-analytics-platform` | **Date**: 2026-09-11 | **Plan**: [plan.md](./plan.md)

A stack foi fornecida no input do comando, então não houve marcador `NEEDS CLARIFICATION` a
resolver. O trabalho desta fase foi outro: submeter cada escolha da stack aos requisitos da spec e
identificar onde o caminho óbvio não entrega o que foi especificado. Sete decisões abaixo; três
delas corrigem o caminho óbvio.

---

## D1 — Idempotência da carga em RAW {#d1}

**Decision**: A ingestão apaga as linhas do lote em RAW e recarrega com `COPY INTO ... FORCE = TRUE`,
dentro de uma transação por tabela. O nome do arquivo no stage é determinístico
(`<entidade>_<data_lote>.csv`) e a coluna `lote_data` identifica o conjunto a substituir.

**Rationale**: O input propôs apoiar a idempotência no histórico de carga do `COPY INTO`. Esse
histórico reconhece um arquivo pelo par nome + ETag e ignora recargas idênticas — o que funciona
enquanto o conteúdo não muda. Mas o gerador é parametrizado por volume e taxa de defeito, e
regerar o dia com outros parâmetros é exatamente o que se faz numa demo. Nesse caso o ETag muda, o
`COPY INTO` carrega de novo e RAW passa a ter as linhas das duas gerações. `SC-002` falharia de
forma intermitente, no pior lugar possível. A substituição por lote torna a idempotência
independente do histórico de carga, que passa a ser otimização e não garantia. Como efeito
colateral bom, a janela de 64 dias de retenção do histórico deixa de importar.

**Alternatives considered**:
- *Só o histórico de carga, sem `FORCE`*: rejeitado — não sobrevive à regeração do lote, como acima.
- *`TRUNCATE` da tabela RAW inteira a cada execução*: rejeitado — destrói o histórico de outros
  dias e impede o cenário de atualização de status vinda em lote posterior (`FR-019a`).
- *Tabelas RAW particionadas por data em nomes distintos*: rejeitado por multiplicar objetos sem
  ganho no volume deste projeto.

**Nota de conformidade**: a tensão com o Princípio III está registrada em
[plan.md § Complexity Tracking](./plan.md#complexity-tracking) e exige ADR. Nenhum `UPDATE` toca
RAW; o conteúdo permanece o CSV como veio, acrescido apenas dos metadados de carga.

---

## D2 — Materialização dos fatos e dos agregados

**Decision**: `fct_apostas` e `fct_transacoes` são incrementais com `unique_key` e
`incremental_strategy = 'merge'`. Os quatro agregados diários (`agg_*`) são tabelas full-refresh a
cada execução.

**Rationale**: `FR-019b` exige que, quando um lote atualiza o status de apostas de datas anteriores,
as métricas de todas as datas afetadas sejam recalculadas. Com agregados incrementais isso obriga a
descobrir o conjunto de datas afetadas e reprocessá-lo — código de backfill que não cabe em 3 dias
e é fonte clássica de bug silencioso. Com agregados full-refresh o problema desaparece por
construção: eles são sempre uma função pura do estado canônico dos fatos. O custo é reconstruir
quatro agregações sobre dezenas de milhares de linhas, o que num warehouse XSMALL leva segundos e
não ameaça o orçamento do trial.

**Alternatives considered**:
- *Agregados incrementais com janela de reprocessamento*: rejeitado pelo custo de complexidade
  contra o Princípio IX, sem ganho mensurável neste volume.
- *Fatos também full-refresh*: rejeitado porque apagaria a demonstração de merge idempotente, que é
  justamente o que `FR-019a` pede e o que um avaliador quer ver.

---

## D3 — Atomicidade de MARTS em caso de falha {#d3}

**Decision**: `dbt build --fail-fast` para cada camada, intercalando modelo e seus testes. Em caso de
falha, a execução para antes de reconstruir os modelos a jusante. Aceita-se o risco residual de
`fct_apostas` ficar à frente dos agregados até a reexecução.

**Rationale**: `FR-020a` pede que, numa falha, as tabelas de métricas permaneçam no estado anterior à
execução. dbt garante atomicidade por modelo — cria em objeto temporário e troca — mas não envolve
a execução inteira numa transação. A alternativa realmente atômica no Snowflake é construir MARTS
num schema paralelo e usar `ALTER SCHEMA ... SWAP WITH`, que é uma única instrução. Ela foi
rejeitada por um motivo concreto: depois do swap, as tabelas incrementais que a próxima execução
leria são as antigas, e o estado incremental de `fct_apostas` se perde. Corrigir isso exigiria
copiar estado entre schemas a cada execução — complexidade desproporcional ao ganho num projeto de
3 dias. Como os agregados são full-refresh e vêm depois dos fatos no grafo, a falha interrompida
deixa o analista vendo os agregados do lote anterior, coerentes entre si, que é o comportamento que
`FR-020a` quer proteger.

**Alternatives considered**:
- *`ALTER SCHEMA SWAP WITH`*: rejeitado pela quebra do estado incremental, acima.
- *Uma transação explícita por execução*: rejeitado — dbt-snowflake não expõe isso, e emulá-lo com
  hooks recria o problema do swap.
- *Ignorar o requisito*: rejeitado — a lacuna é registrada e comunicada, não escondida.

---

## D4 — dbt dentro da imagem do Airflow

**Decision**: A imagem estendida instala dbt-core e dbt-snowflake num virtualenv isolado em
`/opt/dbt-venv`, e o `BashOperator` chama `/opt/dbt-venv/bin/dbt` por caminho absoluto. O projeto
dbt é montado como volume.

**Rationale**: Airflow 2.9 publica um arquivo de restrições que fixa versões de dependências comuns
(`jinja2`, `click`, `packaging`, `urllib3`), e dbt-core exige faixas diferentes de várias delas.
Instalar os dois no mesmo interpretador resolve — quando resolve — num conjunto que quebra um dos
lados em tempo de execução, tipicamente com erro de Jinja difícil de diagnosticar. Um virtualenv
separado dentro da mesma imagem elimina a colisão sem introduzir contêiner novo e mantém o
`BashOperator` pedido no input.

**Alternatives considered**:
- *Instalar dbt ao lado do Airflow*: rejeitado pelo conflito de restrições, que é conhecido e
  reprodutível.
- *`DockerOperator` com imagem dbt própria*: rejeitado por exigir socket do Docker dentro do
  contêiner do Airflow — mais partes móveis e mais um modo de falha na véspera da demo.
- *astronomer-cosmos*: rejeitado pelo Princípio IX e pelo input, que pediu `BashOperator` por
  simplicidade. Supersede o ADR 0003 do escopo antigo.

---

## D5 — Determinismo do gerador

**Decision**: Uma única semente propaga para `Faker.seed()`, `random.seed()` e para qualquer
gerador auxiliar. A escrita CSV é determinística: ordem de colunas fixa, ordenação final das linhas
pela chave natural, decimais com duas casas e ponto como separador, datas em ISO-8601, terminador de
linha `\n` explícito. Um teste calcula o checksum de duas gerações com a mesma semente e exige
igualdade.

**Rationale**: O Princípio VI e `SC-002` cobram reprodutibilidade por checksum, não "quase igual".
Três coisas quebram isso silenciosamente: `Faker` instanciado sem semente compartilhada; iteração
sobre `set` ou `dict` sem ordenação explícita; e `csv.writer` em Windows, que escreve `\r\n` e
muda o checksum entre plataformas. As três são tratadas por desenho, não por convenção.

**Alternatives considered**:
- *Semear apenas o `Faker`*: rejeitado — o `random` do módulo padrão, usado para sorteio de status
  e de defeitos, ficaria fora e reintroduziria variação.
- *Comparar amostras em vez de checksum*: rejeitado por não ser verificação, e sim impressão.

---

## D6 — Marcador de atualização e resolução de duplicatas

**Decision**: Toda entidade gerada carrega `atualizado_em` (timestamp UTC). A deduplicação em STAGING
usa `ROW_NUMBER()` particionado pela chave natural, ordenado por `atualizado_em DESC` e, como
desempate, pelas demais colunas em ordem fixa. A mesma expressão de ordenação alimenta o `merge` dos
fatos, de modo que "vence o mais recente" seja uma regra só, dentro e entre lotes.

**Rationale**: `FR-005` e `FR-019a` foram fixados nas clarificações e pedem exatamente isto. O
desempate por colunas restantes existe porque o gerador pode emitir duas versões com o mesmo
`atualizado_em`; sem ele, `ROW_NUMBER()` escolheria arbitrariamente e `SC-002` falharia de forma
intermitente — o modo de falha mais caro de diagnosticar.

**Alternatives considered**:
- *`QUALIFY ROW_NUMBER()` sem desempate secundário*: rejeitado pela não-determinância no empate.
- *`DISTINCT` sobre todas as colunas*: rejeitado — resolve duplicata idêntica e não resolve
  divergente, que é o caso interessante.

---

## D7 — Quarentena e fronteira de dia

**Decision**: Um modelo de quarentena por entidade (`stg_<entidade>_rejeitadas`) preserva o registro
original em coluna `VARIANT`, com `lote_data`, `rejeitado_em` e `motivos` como array. Uma view
`qua_registros_rejeitados` une os quatro e alimenta `agg_qualidade_lote`. Todas as datas do
pipeline são `DATE` em UTC; a data lógica do lote vem do `{{ ds }}` do Airflow.

**Rationale**: `FR-010` exige conteúdo original, lote, momento e todos os motivos aplicáveis;
`FR-016` exige contagem por motivo e por entidade. `VARIANT` no Snowflake guarda o registro original
sem precisar de uma tabela de quarentena por forma de esquema, e o array de motivos atende o caso de
borda do registro que viola mais de uma regra sendo contado uma vez (`US2`, cenário 4). A view de
união dá a quebra por entidade sem duplicar lógica de agregação. UTC em tudo elimina o caso de borda
da fronteira de dia por construção, em vez de por regra documentada.

**Alternatives considered**:
- *Tabela única de quarentena escrita pelos quatro modelos*: rejeitado — no dbt, vários modelos
  escrevendo no mesmo objeto quebra a linhagem e a atomicidade por modelo.
- *Coluna booleana de invalidez na própria tabela de STAGING*: rejeitado porque violaria `FR-011`:
  registro inválido continuaria a um `WHERE` esquecido de distância das métricas.
- *Timezone de São Paulo nas datas*: rejeitado pelo Princípio IX — introduz conversão e horário de
  verão histórico num projeto de 3 dias, sem ganho analítico em dado sintético.

---

## Riscos abertos

| Risco | Impacto | Mitigação |
|---|---|---|
| Crédito do trial do Snowflake esgotar antes da apresentação | Bloqueia a demo | XSMALL + `AUTO_SUSPEND = 60`; consultas exploratórias no mínimo; conferir crédito restante no fim de cada dia |
| Primeira subida do Airflow em Docker consumir metade do dia 1 | Comprime o cronograma | Subir o Compose como primeira tarefa do dia 1, antes de escrever gerador; validar com uma DAG trivial |
| `fct_apostas` à frente dos agregados após falha (D3) | Inconsistência transitória visível | Documentado no dicionário de métricas; a reexecução resolve; não bloqueia nenhum critério de sucesso |
| Dashboard opcional virar atrativo e roubar tempo do ensaio | Demo sem ensaio | Princípio IX: o dashboard só começa depois do ensaio gravado |
