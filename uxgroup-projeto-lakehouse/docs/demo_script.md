# Roteiro da demonstração — 10 minutos

**Regra número um**: ensaie com cronômetro antes. Um roteiro não ensaiado é um roteiro que estoura.

**Antes de começar**: `make up` já rodado, Airflow verde em <http://localhost:8080>, uma aba do
Snowsight aberta em `BETS`, e **um lote do dia anterior já processado** — é ele que dá o contraste
nos minutos 6 e 8.

---

## 0:00 – 1:00 · O problema

> "Uma casa de apostas precisa saber todo dia quanto ganhou, quanto foi apostado e quantos
> apostadores estiveram ativos. O problema não é calcular — é que o dado operacional chega sujo:
> apostas duplicadas, campos nulos, valores negativos, datas de aposta depois do jogo já ter
> acontecido."

> "Publicar métrica sobre esse material dá número errado com cara de número certo. É disso que o
> projeto trata."

Mostre o diagrama do README. Não passe de um minuto aqui.

---

## 1:00 – 3:00 · O pipeline rodando

```bash
make run DATA=2026-09-11
```

Enquanto a DAG roda, narre as seis tarefas na interface do Airflow:

> "Um comando. Gera o lote, carrega em RAW sem transformar nada, limpa em STAGING, testa, monta as
> métricas em MARTS, testa de novo. Não há passo manual entre elas."

Aponte que **RAW guarda tudo como VARCHAR**:

> "Nenhuma coluna de RAW é tipada. É de propósito: sem conversão, não existe conversão que falhe.
> Uma aposta com valor negativo chega inteira até a quarentena em vez de derrubar a carga."

---

## 3:00 – 5:00 · A resposta de negócio

```sql
SELECT data_aposta, esporte, total_apostado, premios_pagos, ggr, exposicao_pendente
FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE
WHERE data_aposta = '2026-09-11'
ORDER BY ggr DESC;
```

> "GGR por dia e por esporte. Total apostado menos prêmios pagos, considerando só apostas
> resolvidas."

Se houver linha com GGR negativo, **pare nela**:

> "Esse dia deu prejuízo em tênis. O pipeline não trunca em zero — um dia negativo é justamente o
> que interessa investigar."

E aponte a última coluna:

> "Exposição pendente fica numa coluna separada e nunca é somada ao GGR. Um é receita realizada, o
> outro é dinheiro em risco que ainda não resolveu. Misturar os dois seria inventar receita."

---

## 5:00 – 7:00 · O que foi descartado — o ponto alto

```sql
SELECT entidade, motivo, qtd_rejeitados, taxa_rejeicao
FROM BETS.MARTS.AGG_QUALIDADE_LOTE
WHERE lote_data = '2026-09-11'
ORDER BY qtd_rejeitados DESC;
```

> "Todo registro que não entrou nas métricas está contado aqui, por motivo. E não foi apagado."

```sql
SELECT entidade, chave_natural, motivos, arquivo_origem, linha_origem, registro_original
FROM BETS.STAGING.QUA_REGISTROS_REJEITADOS
WHERE lote_data = '2026-09-11'
  AND ARRAY_CONTAINS('valor_nao_positivo'::VARIANT, motivos)
LIMIT 3;
```

> "Aqui está o registro como veio, o arquivo e a linha exata do CSV. Dá para voltar de uma métrica
> suspeita até o dado de origem."

Feche com o invariante:

> "Recebidos igual a aceitos mais rejeitados, em toda entidade e todo lote. É um teste que roda no
> pipeline: se um registro sumisse no caminho, a execução falhava."

---

## 7:00 – 8:30 · Sujeira extrema não derruba nada — e é por isso que é confiável

Dispare uma execução com sujeira extrema:

```bash
docker compose exec -T airflow-scheduler airflow dags trigger pipeline_bets \
  --conf '{"taxa_nulos": 0.9}'
```

> "Noventa por cento de nulos nos campos obrigatórios."

Mostre a DAG inteira verde, ponta a ponta — nenhuma tarefa vermelha.

> "A execução termina com sucesso. Nada crashou, nada travou. Os 90% de lixo foram pra quarentena
> antes de chegar em qualquer tabela testada — é por isso que não há nada pra quebrar aqui: um
> registro com campo obrigatório nulo nunca entra em `stg_apostas`, então nenhum teste de
> não-nulidade tem o que reprovar. A taxa de rejeição fica registrada em `agg_qualidade_lote`, mas
> ela é informativa, nunca um bloqueio — isso é `FR-016a` funcionando como projetado, não um
> limite do sistema."

**O que bloqueia de verdade não é taxa — é teste estrutural**, e isso já aconteceu de verdade
durante a construção deste projeto, não é encenação:

> "Rodar isso pela primeira vez contra o Snowflake real — o que fiz só esta semana — pegou dois
> bugs genuínos que nenhum parse de SQL detectaria: apostas ficando órfãs de dimensão ao reprocessar
> um lote com volume diferente, e testes de integração se contaminando entre si no mesmo warehouse.
> Os dois foram pegos exatamente pelos testes estruturais — `relationships_fct_apostas_evento_id`
> e as asserções de FR-019 — que abortaram a execução exatamente como `FR-020` exige. Estão
> documentados no histórico e no ADR 0006."

Se quiser mostrar um bloqueio ao vivo em vez de só narrar: tenha preparado, antes da demo, um commit
`git stash` com uma quebra estrutural real (ex.: comentar uma coluna obrigatória em
`stg_apostas.sql`), aplicar com `git stash pop`, rodar, mostrar vermelho, e `git checkout --` para
reverter. Não improvise isso ao vivo sem ensaiar — é o tipo de passo que trava uma demo.

---

## 8:30 – 9:30 · Idempotência e correção retroativa

```bash
make run DATA=2026-09-11
```

> "Mesmo lote de novo. Nenhum número muda — nem uma linha a mais em RAW."

Depois:

```sql
SELECT data_aposta, ggr, exposicao_pendente
FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE
WHERE data_aposta = '2026-09-10';
```

> "Esse é o GGR de ontem, e ele mudou desde ontem. Apostas que estavam pendentes foram resolvidas
> no lote de hoje. O fato faz merge pela chave da aposta, e os agregados são reconstruídos — então
> a data antiga é recalculada sozinha, sem código de backfill. A aposta continua aparecendo uma
> vez só."

---

## 9:30 – 10:00 · Fechamento

> "Custo zero: conta trial do Snowflake, warehouse no menor tamanho, suspende sozinho em 60
> segundos. Todo o resto é open-source local."

> "Dados 100% sintéticos, com semente fixa: quem clonar o repositório vê exatamente estes
> números."

> "E o que eu não fiz: tempo real e machine learning estão fora do escopo por escolha. Em três
> dias, o fluxo completo funcionando vale mais do que uma parte sofisticada."

---

## Se perguntarem

**"Por que dbt e não SQL puro?"** — Testes de dados como cidadãos de primeira classe, linhagem
gerada do código e materialização incremental sem escrever `MERGE` à mão.

**"E se o lote chegar duas vezes?"** — A carga apaga as linhas daquela data lógica e recarrega. Não
depende do histórico do `COPY INTO`, que só reconhece nome e ETag do arquivo — se eu regerar o
mesmo dia com outro volume, o histórico deixaria passar e duplicaria. Está no ADR 0006.

**"Como sei que os dados são reprodutíveis?"** — Teste que gera o mesmo lote duas vezes e compara
checksum SHA-256 arquivo por arquivo.

**"Qual a maior limitação?"** — dbt não envolve uma execução inteira em transação. Se um teste
reprovar entre os fatos e os agregados, `fct_apostas` fica momentaneamente à frente. A alternativa
atômica (`ALTER SCHEMA SWAP`) quebra o estado incremental. Está documentado, não escondido.

**"O que faria com mais tempo?"** — Dashboard sobre os marts, alerta quando a taxa de rejeição
desvia do histórico, e snapshot do GGR para quem precisar de número congelado.
