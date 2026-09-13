# Phase 0 — Pesquisa e Verificação das Fontes

**Feature**: 001-brand-mention-intelligence
**Data da verificação**: 2026-09-08
**Método**: consulta à documentação oficial de cada fonte antes de qualquer linha de código,
conforme exigido no enunciado do plano e pelo Princípio I da constituição.

> **Regra de leitura**: tudo nesta página marcado como **CONFIRMADO** foi lido na documentação
> oficial e está com a fonte linkada. Tudo marcado como **VERIFICAR EM EXECUÇÃO** não pôde ser
> resolvido por documentação e exige um comando real contra a fonte antes do código depender
> disso. Nada aqui é presumido.

---

## 1. GDELT DOC 2.0 API — CONFIRMADO

Fonte: [GDELT DOC 2.0 API Debuts](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)

### Parâmetros de URL

| Parâmetro | Valores confirmados |
|-----------|--------------------|
| `query` | String de busca contendo os operadores (ver abaixo) |
| `mode` | `ArtList`, `TimelineVol`, `TimelineVolRaw`, `TimelineVolInfo`, `TimelineTone`, `TimelineLang`, `TimelineSourceCountry`, `ToneChart`, e modos de imagem |
| `format` | `HTML` (default), `CSV`, `RSS`, `JSON`, `JSONP`, `JSONFeed` |
| `timespan` | `<número><unidade>`, unidades `min`, `h`/`hours`, `d`/`days`, `w`/`weeks`, `m`/`months` |
| `startdatetime` / `enddatetime` | `YYYYMMDDHHMMSS` |
| `maxrecords` | **default 75, máximo 250** — aplica-se apenas a `ArtList` e `ImageCollage` |
| `sort` | `DateDesc`, `DateAsc`, `ToneDesc`, `ToneAsc`, `HybridRel` (default) |
| `timelinesmooth` | até 30 passos |

### Operadores — vão DENTRO do valor de `query`, nunca como parâmetro próprio

Este ponto era um dos VERIFICAR do enunciado e está **confirmado**: todos os operadores abaixo
são parte da string de `query`, separados por espaço.

| Operador | Sintaxe exata |
|----------|---------------|
| Frase exata | `"donald trump"` |
| OR booleano | `(clinton OR sanders OR trump)` |
| Negação | `-sourcelang:spanish` |
| Proximidade | `near20:"trump putin"` |
| Repetição | `repeat3:"trump"` |
| Domínio | `domain:cnn.com` |
| Domínio exato | `domainis:un.org` |
| Idioma da fonte | `sourcelang:spanish` |
| País da fonte | `sourcecountry:france` (sem espaços: `saudiarabia`) |
| Tema GKG | `theme:TERROR` |
| Tom | `tone<-5`, `tone>5`, `toneabs>10` |

### Janela temporal

**CONFIRMADO**: janela móvel de **3 meses**. `startdatetime`/`enddatetime` precisam cair dentro
dos últimos 3 meses. Isto casa exatamente com a janela de monitoramento ativo da spec (SC-001) e
**confirma que a linha de base de 12 meses (SC-002) é impossível por esta API** — ela só pode vir
do BigQuery.

### Limite de requisições

Fonte: [Ukraine, API Rate Limiting & Web NGrams 3.0](https://blog.gdeltproject.org/ukraine-api-rate-limiting-web-ngrams-3-0/)

**PARCIAL**. O GDELT declara oficialmente que "our APIs are rate limited to protect the underlying
ElasticSearch clusters" e que isso se aplica às APIs DOC e Context 2.0, mas **não publica o número**.
A prática da comunidade converge para ~1 requisição a cada 5 segundos.

**Decisão**: adotar 1 requisição a cada 5 segundos, em série, como default conservador do projeto,
documentado explicitamente como escolha nossa e não como número oficial do GDELT. O Princípio II
manda ser bom cidadão; na dúvida sobre o limite, a folga é nossa responsabilidade.

### Licença e atribuição — CONFIRMADO

Fonte: [GDELT About](https://www.gdeltproject.org/about.html)

> "available for unlimited and unrestricted use for any academic, commercial, or governmental use
> of any kind without fee"
> "Any use or redistribution of the data must include a citation to the GDELT Project and a link
> to this website (https://www.gdeltproject.org/)."

Atende ao Princípio XII. A citação e o link vão no README e no rodapé da documentação gerada.

### Cliente Python existente

Fonte: [alex9smith/gdelt-doc-api](https://github.com/alex9smith/gdelt-doc-api) · [PyPI `gdeltdoc`](https://pypi.org/project/gdeltdoc/)

Última versão 1.12.0, manutenção ativa, publicação automatizada por GitHub Actions.
Existe issue aberta especificamente sobre tratamento da resposta de rate limit
([#22](https://github.com/alex9smith/gdelt-doc-api/issues/22)) — ou seja, o backoff dele não é
confiável para o nosso caso.

**Decisão**: **não adotar** como dependência. O Princípio II exige User-Agent com contato, backoff
com jitter, teto de tentativas, limite de requisições por execução e cache em disco — o conjunto
inteiro é justamente o que precisamos controlar, e o cliente não o entrega. Vamos implementar um
cliente próprio fino sobre `requests`, e usar o `gdeltdoc` apenas como **referência de leitura**
para a construção das URLs. Vira ADR de ferramenta descartada (Princípio X).

---

## 2. GDELT no BigQuery — CONFIRMADO com ressalva

Fonte: [Announcing Partitioned GDELT BigQuery Tables](https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/)

### Tabelas particionadas — nomes exatos confirmados

- `gdelt-bq.gdeltv2.gkg_partitioned` ← **a que nos interessa** (cobertura noticiosa, tom, tema)
- `gdelt-bq.gdeltv2.events_partitioned`
- `gdelt-bq.gdeltv2.eventmentions_partitioned`
- `gdelt-bq.gdeltv1.events_partitioned`

### Pseudo-coluna de partição — sintaxe exata confirmada

```sql
_PARTITIONTIME >= TIMESTAMP("2016-06-01") AND _PARTITIONTIME <= TIMESTAMP("2016-06-15")
```

### Ganho de custo comprovado pela própria fonte

O anúncio documenta uma consulta que, na variante particionada, varreu **15 GB em 2 segundos**
contra **423 GB em 8,6 segundos** na variante não particionada — fator ~28×. É a evidência que
sustenta o Princípio I.

### Ressalva importante

O anúncio **não** documenta frequência de atualização, completude frente às tabelas não
particionadas, nem garantias de manutenção. As tabelas foram anunciadas "for the moment".

**VERIFICAR EM EXECUÇÃO (bloqueante)**: confirmar que `gkg_partitioned` ainda recebe dados
recentes. Comando de verificação, custo zero por ser metadado:

```sql
SELECT MAX(_PARTITIONTIME) AS ultima_particao
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
```

Se a última partição estiver defasada em mais de alguns dias, o plano B é a tabela não
particionada `gdelt-bq.gdeltv2.gkg` **restrita por partição de data via coluna `DATE`** — o que
custa muito mais bytes e obriga a reduzir a linha de base de 12 para 3 ou 6 meses. Decisão vai
para ADR.

### Colunas — VERIFICAR EM EXECUÇÃO

A documentação de esquema confirma a existência de `DocumentIdentifier` (URL do documento),
`V2SourceCommonName` (domínio do veículo), `V2Themes` e `V2Tone`
([GKG Codebook V2.1](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)).

**Não confirmado por documentação**: os nomes exatos das colunas *na tabela BigQuery*
`gkg_partitioned`, que podem divergir do codebook do arquivo bruto. Verificar com:

```bash
bq show --schema --format=prettyjson gdelt-bq:gdeltv2.gkg_partitioned
```

**Lacuna identificada — país do veículo**: o GKG **não** traz país da fonte como coluna direta;
traz o domínio em `V2SourceCommonName`. O recorte `share_of_voice_brasil` (FR-020) depende de
mapear domínio → país. Três caminhos, a decidir em ADR após verificação:

1. Derivar de ccTLD (`.br`) — simples, perde veículo brasileiro em `.com`.
2. Usar a lista de domínios por país publicada pelo GDELT — precisa ser localizada e versionada.
3. Usar o operador `sourcecountry:brazil` da DOC API para construir o cadastro de veículos
   brasileiros, e usar esse cadastro como dimensão no BigQuery.

**Recomendação**: caminho 3. Ele usa a classificação do próprio GDELT (mesma taxonomia das duas
fontes), custa zero byte de BigQuery e produz um cadastro de veículos versionado que já é
exigido por FR-019.

---

## 3. BigQuery — custo, free tier e a decisão mais importante do plano

### Free tier — CONFIRMADO

Fontes: [BigQuery Sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox) ·
[BigQuery pricing](https://cloud.google.com/bigquery/pricing)

- **1 TiB de dados processados por consulta, por mês, grátis** — permanente, não é trial.
- **10 GiB de armazenamento ativo por mês, grátis**.
- Acima disso: **US$ 6,25 por TiB** varrido (on-demand).
- **Dry run não é cobrado** — é a base da trava (a) do Princípio I.

### CONFLITO DURO — o sandbox bloqueia DML

**CONFIRMADO**: o BigQuery Sandbox dispensa cartão de crédito e aplica os limites do free tier,
mas **bloqueia statements DML (INSERT, UPDATE, DELETE)**, bloqueia streaming inserts e expira
todas as tabelas, views e partições em **60 dias**, sem possibilidade de alterar a expiração.

Isso colide de frente com o plano: **`incremental` do dbt no BigQuery usa `MERGE`, que é DML**.
No sandbox, os fatos incrementais com merge exigidos por FR-030/FR-031 e pela História 5
simplesmente não rodam.

**As duas saídas, e a recomendação:**

| Opção | Como fica | Consequência |
|-------|-----------|--------------|
| **A — Projeto com billing habilitado + free tier** (recomendada) | DML funciona, dbt incremental funciona, sem expiração de 60 dias | Exige cartão. Risco de cobrança passa a ser real e precisa ser eliminado por trava técnica, não por disciplina |
| B — Sandbox, sem cartão | Cobrança é **tecnicamente impossível** | Todos os modelos viram `table` (full refresh, DDL). FR-030/FR-031 perdem o merge; a idempotência passa a ser trivial e a História 5 perde o conteúdo técnico que a torna defensável |

**Decisão: opção A**, com **quatro travas cumulativas em vez das três do enunciado**:

1. **Cota de projeto no BigQuery**: `Query usage per day` limitada (ex.: 50 GiB/dia) no painel de
   quotas. Esta é a trava mais forte disponível fora do sandbox — é limite de projeto, nenhuma
   query a contorna, e é exatamente o que o Princípio I pede ao dizer "o teto é configuração do
   projeto, não escolha de quem escreve a query".
2. **`maximum_bytes_billed`** na configuração de todo job, lido de config central.
3. **Dry run obrigatório** antes de toda execução real, com bytes estimados em log.
4. **Validação programática de filtro de partição** antes do envio — a query nem chega ao BigQuery
   sem `_PARTITIONTIME`.

Mais: alerta de orçamento em R$ 0,01 no billing. O sandbox vira **ADR de alternativa descartada**,
com o motivo registrado (bloqueio de DML), conforme Princípio X.

### Orçamento de bytes — VERIFICAR EM EXECUÇÃO (o item mais crítico do plano)

Nenhuma estimativa de bytes para as nossas consultas específicas pode ser obtida de documentação.
**Procedimento obrigatório antes da extração histórica**, nesta ordem:

```bash
# 1. Dry run de UM ÚNICO DIA, com as colunas mínimas
bq query --use_legacy_sql=false --dry_run \
  'SELECT DATE, DocumentIdentifier, V2SourceCommonName, V2Tone
   FROM `gdelt-bq.gdeltv2.gkg_partitioned`
   WHERE _PARTITIONTIME = TIMESTAMP("2026-06-01")'
# 2. Multiplicar o resultado por 365 e comparar com o orçamento
# 3. Só então decidir o tamanho da janela histórica
```

**Orçamento definido para o projeto**: no máximo **200 GiB varridos no total do projeto**, ou seja
20% do 1 TiB mensal gratuito, deixando 80% de folga para erro humano e reexecução. Se a
extrapolação do passo 2 estourar os 200 GiB, o plano B é, nesta ordem: (i) reduzir colunas,
(ii) reduzir a linha de base de 12 para 6 meses e registrar o desvio de SC-002 na documentação,
(iii) amostrar dias (ex.: um a cada 3) para a linha de base, declarando a amostragem na métrica.

---

## 4. CONFLITO ENTRE A SPEC E A REALIDADE DA API — `maxrecords` = 250

**Este é o achado que mais muda o desenho.**

FR-023 da spec exige que "a soma das menções listadas em um dia coincida com o volume absoluto
daquele dia na série agregada". Mas o `ArtList` da DOC 2.0 devolve **no máximo 250 artigos por
chamada, e a API não tem parâmetro de paginação ou offset**. Não existe como enumerar
exaustivamente um dia de alto volume por essa via.

**Resolução desenhada** (mantém FR-023 verificável em vez de abandoná-lo):

| Necessidade | Mecanismo | Por quê |
|-------------|-----------|---------|
| Volume contável por marca/dia (numerador) | `mode=TimelineVolRaw` — contagem real de artigos | Uma requisição cobre o período inteiro; não sofre teto de 250 |
| Denominador da categoria | `mode=TimelineVolRaw` com a query da categoria | Mesma mecânica, mesmo período |
| Menções individuais para drill-down | `mode=ArtList`, uma requisição por marca por dia | Volume diário por marca deve ficar bem abaixo de 250 |
| Reconciliação FR-023 | Comparar contagem do `ArtList` com o valor do `TimelineVolRaw` do mesmo dia | A diferença é medida e reportada, não escondida |
| Truncamento | Se `ArtList` devolver exatamente 250, fatiar o dia em subjanelas por `startdatetime`/`enddatetime` e repetir | Única forma de paginar nesta API |

Isso transforma FR-023 de "os números batem" para "os números batem, e quando não batem o
sistema diz de quanto e por quê" — que é mais honesto e continua testável.

**Impacto no SC-006 (pipeline em menos de 20 minutos)**: a carga inicial de 7 marcas × 90 dias =
630 requisições a 5 s/requisição ≈ **53 minutos**. Isso **excede** o SLA.

**Resolução**: o SC-006 passa a valer para o **ciclo diário incremental** (7 requisições + dbt +
testes), que cabe folgadamente em 20 minutos. A carga inicial de 3 meses roda uma vez, em DAG
separado de backfill, junto da extração histórica do BigQuery. Isso precisa ser refletido na spec.

---

## 5. Fonte secundária (SHOULD) — SPA/MF — PARCIAL

Fonte: [Transparência Ativa – Processos de Autorização](https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/lista-de-empresas) ·
[Secretaria de Prêmios e Apostas](https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas)

**Confirmado**: a SPA/MF é o órgão autorizador; existem as seções "Empresas Autorizadas" e
"Autorizadas por Determinação Judicial"; desde 01/01/2025 apenas autorizadas operam e todas usam
o domínio `.bet.br` — o que **valida a âncora de domínio da Camada 1** como identificador canônico.

**VERIFICAR EM EXECUÇÃO**: a página não expõe, no conteúdo lido, um arquivo CSV/XLSX estável com
campos estruturados nem data de atualização. Antes de codar o ingestor desta fonte, abrir a página
e confirmar se há download estruturado.

**Plano B se não houver arquivo estruturado**: como esta fonte é SHOULD e alimenta apenas o
enriquecimento da dimensão de marca (razão social, CNPJ, domínio autorizado) para **7 marcas**,
transcrever manualmente uma vez para um `seed` CSV versionado, com `data_de_referencia` e a URL
da consulta registradas. Sete linhas transcritas à mão, versionadas e datadas, são honestas e
custam 20 minutos; um raspador de página `gov.br` para sete linhas viola o Princípio VIII
(solução mais simples que atende) e flerta com o Princípio XII.

---

## 6. Fonte opcional (COULD) — Wikimedia Pageviews — NÃO VERIFICADO

Deliberadamente não pesquisado em profundidade. É COULD, está atrás do portão do dia 5, e é o
**primeiro item da fila de corte** da spec. Pesquisar agora gastaria orçamento de dia contra o
item de menor probabilidade de entrega. Se o portão do dia 5 abrir, verificar então: endpoint
REST, exigência de User-Agent, limites e licença.

---

## 7. Orquestração — dbt no Airflow

Fonte: [astronomer/astronomer-cosmos](https://github.com/astronomer/astronomer-cosmos) ·
[Astronomer Docs](https://www.astronomer.io/docs/learn/airflow-dbt)

**Confirmado**: o Cosmos renderiza projetos dbt Core como DAGs e TaskGroups do Airflow, com
`DbtTaskGroup` criando uma task Airflow por modelo dbt, incluindo execução de testes após a
materialização de cada modelo. Isso atende diretamente à exigência "cada modelo dbt aparece como
tarefa observável no grafo, não como comando opaco".

**Decisão**: adotar `astronomer-cosmos`. Alternativa descartada: `BashOperator` chamando
`dbt build`, que produziria uma única caixa-preta no grafo e violaria o Princípio XI
(observabilidade por modelo). Vira ADR.

---

## 8. Decisões consolidadas

| # | Decisão | Justificativa | Alternativa descartada |
|---|---------|---------------|------------------------|
| D1 | DOC 2.0 para a janela ativa de 3 meses; BigQuery GKG para a linha de base de 12 meses | A DOC 2.0 tem janela móvel de 3 meses confirmada — 12 meses é impossível por ela | Usar só uma das duas fontes |
| D2 | Cliente HTTP próprio, `gdeltdoc` apenas como referência | Princípio II exige controle de UA, backoff, cache e limite | Depender de `gdeltdoc` |
| D3 | 1 requisição / 5 s, em série | GDELT não publica o número; a folga é nossa responsabilidade | Paralelizar |
| D4 | Projeto BigQuery com billing + 4 travas cumulativas | Sandbox bloqueia DML e mata o dbt incremental | BigQuery Sandbox |
| D5 | Cota diária de bytes no projeto como trava primária | É limite de projeto que nenhuma query contorna | Só `maximum_bytes_billed` |
| D6 | Orçamento total de 200 GiB (20% do free tier) | 80% de folga para erro e reexecução | Usar o 1 TiB inteiro |
| D7 | `TimelineVolRaw` para contagem; `ArtList` para detalhe; reconciliação medida | `maxrecords` teto de 250 sem paginação | Contar somando `ArtList` |
| D8 | SC-006 (20 min) vale para o ciclo diário; backfill em DAG separado | 630 requisições × 5 s ≈ 53 min | Manter o SLA sobre o backfill |
| D9 | Cadastro de veículos brasileiros via `sourcecountry:brazil` da DOC API | GKG não tem país da fonte; custo zero de BigQuery | Derivar de ccTLD |
| D10 | SPA/MF como seed CSV transcrito e datado, se não houver arquivo estruturado | 7 linhas; raspar `gov.br` viola Princípios VIII e XII | Raspador de página |
| D11 | `astronomer-cosmos` para dbt no Airflow | Task por modelo dbt, exigida pelo Princípio XI | `BashOperator` com `dbt build` |

---

## 9. Bloqueadores antes da primeira linha de código

Executar nesta ordem. Nenhum código de ingestão ou transformação começa antes de todos passarem.

| # | Verificação | Comando / ação | Se falhar |
|---|-------------|----------------|-----------|
| V1 | `gkg_partitioned` ainda atualizada | `SELECT MAX(_PARTITIONTIME) ...` (metadado, custo zero) | Plano B: `gkg` com filtro de `DATE` e janela reduzida; ADR |
| V2 | Esquema real da tabela | `bq show --schema gdelt-bq:gdeltv2.gkg_partitioned` | Ajustar nomes de coluna no staging |
| V3 | **Custo em bytes de 1 dia** | `bq query --dry_run` conforme §3 | Reduzir colunas → reduzir janela → amostrar |
| V4 | Cota diária de query configurada no projeto | Painel de quotas do GCP | Não prosseguir. É a trava primária |
| V5 | `maximum_bytes_billed` faz a query falhar | Query deliberadamente grande com teto baixo; deve dar erro, não cobrança | Não prosseguir |
| V6 | DOC 2.0 responde com os modos e operadores previstos | 1 requisição real por modo, salva como fixture | Ajustar o cliente ao que existir |
| V7 | Volume diário por marca < 250 no `ArtList` | 1 requisição para a marca de maior volume | Ativar fatiamento por subjanela |
| V8 | Resposta real do rate limit | Observar cabeçalho/corpo ao ser limitado | Calibrar o backoff ao que vier |
| V9 | Arquivo estruturado na SPA/MF | Abrir a página | Plano B: seed CSV transcrito e datado |

---

## 10. Impactos na spec que exigem decisão

Dois pontos em que a realidade das fontes contraria o que a spec afirma. O Princípio Governança
manda a constituição prevalecer sobre a spec, e manda sinalizar conflito em vez de silenciar:

1. **FR-023** (soma das menções listadas = volume da série) precisa ser reescrito para o modelo de
   reconciliação medida do §4, porque a API não permite enumeração exaustiva.
2. **SC-006** (pipeline completo em menos de 20 minutos) precisa distinguir ciclo diário
   incremental de carga inicial, porque o teto de requisições torna o backfill de 3 meses
   incompatível com 20 minutos.

Ambos estão registrados na seção *Riscos e conflitos* do `plan.md` e precisam de decisão do autor
antes de `/speckit.tasks`.
