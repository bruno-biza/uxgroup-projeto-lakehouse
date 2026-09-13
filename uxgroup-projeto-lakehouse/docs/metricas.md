# Dicionário de métricas

Todas as métricas deste projeto são calculadas sobre **dados sintéticos**, gerados por código a
partir de uma semente fixa. Nenhum número aqui descreve uma operação real.

Cada métrica declara o que inclui e — mais importante — o que **não** inclui. Uma métrica
apresentada além do que o dado sustenta é erro analítico, e o jeito de evitá-lo é escrever o
limite junto com o número.

O mesmo texto está nas descrições do `schema.yml` do dbt, então a documentação gerada carrega as
mesmas ressalvas.

---

## `agg_ggr_diario_esporte`

**Pergunta que responde**: quanto a casa ganhou num dia, por esporte.

**Grão**: uma linha por `data_aposta` × `esporte`.

| Coluna | Definição |
|---|---|
| `total_apostado` | Soma de `valor_apostado` das apostas com status `ganha` ou `perdida` |
| `premios_pagos` | Soma de `premio_pago` das mesmas apostas |
| `ggr` | `total_apostado − premios_pagos`. **Pode ser negativo** |
| `exposicao_pendente` | Valor apostado em apostas ainda `pendente` |
| `qtd_apostas_resolvidas` | Contagem das apostas que entraram no GGR |

**Inclui**: apenas apostas válidas — aprovadas em todas as regras de qualidade — com status
`ganha` ou `perdida`.

**Não inclui**:

- apostas `cancelada`: o valor é devolvido ao apostador, não há receita;
- apostas `pendente` nas três colunas de receita — elas aparecem só em `exposicao_pendente`;
- nenhum registro em quarentena;
- custo operacional, imposto, bônus ou comissão. **GGR é receita bruta de jogo, não lucro.**

**Nunca faça**: somar `ggr` com `exposicao_pendente`. São grandezas de naturezas diferentes — uma
é receita realizada, a outra é dinheiro em risco ainda não resolvido. A separação foi decisão
explícita, registrada em `specs/002-betting-analytics-platform/spec.md`.

**Volatilidade**: o `ggr` de uma data passada **muda** quando uma aposta daquela data sai de
`pendente` num lote posterior. Esta tabela é sempre a melhor leitura disponível daquele dia, não
um fechamento contábil. Quem precisar de um número congelado precisa congelá-lo fora daqui.

**Por que o GGR pode ser negativo**: com odd média acima de 2, um dia com muitas apostas ganhas
custa à casa mais do que arrecadou. Isso é normal no negócio e o pipeline não trunca o valor em
zero — truncar esconderia justamente o dia que mais interessa investigar.

---

## `agg_engajamento_diario`

**Pergunta que responde**: quanta atividade houve num dia.

**Grão**: uma linha por `data_aposta`.

| Coluna | Definição |
|---|---|
| `volume_apostado` | Soma de `valor_apostado` de **todas** as apostas válidas |
| `ticket_medio` | Média do valor apostado. **Nulo**, nunca zero, quando não há aposta |
| `apostadores_ativos` | Contagem distinta de apostadores com ao menos uma aposta na data |
| `qtd_apostas` | Contagem de apostas válidas |

**Inclui**: todas as apostas válidas, independentemente de status — inclusive `pendente` e
`cancelada`. É métrica de **atividade**, não de receita, e o critério difere do GGR de propósito.

**Não inclui**: registros em quarentena; apostadores sem aposta na data (não são "ativos");
acessos, sessões ou logins — esse dado não existe no escopo.

⚠️ **Atenção**: `volume_apostado` **não é comparável** a `total_apostado` de
`agg_ggr_diario_esporte`, porque aquele exclui pendentes e canceladas e este não. Comparar os dois
sem essa ressalva é o erro de leitura mais provável de todo o projeto.

**Por que `ticket_medio` é nulo e não zero**: zero afirmaria que o ticket médio do dia foi zero.
O correto, num dia sem apostas, é que não existe ticket médio. Afirmar zero levaria qualquer média
de médias a subestimar o valor.

---

## `agg_financeiro_diario`

**Pergunta que responde**: entrou mais dinheiro do que saiu num dia.

**Grão**: uma linha por `data_transacao`.

| Coluna | Definição |
|---|---|
| `total_depositado` | Soma dos valores com `tipo = 'deposito'` |
| `total_sacado` | Soma dos valores com `tipo = 'saque'` |
| `liquido` | `total_depositado − total_sacado`. **Pode ser negativo** |
| `qtd_depositos`, `qtd_saques` | Contagens por tipo |

**Inclui**: transações válidas de depósito e saque.

**Não inclui**: saldo de conta do apostador (não é modelado); estornos e chargebacks (fora do
escopo); **qualquer relação com o GGR**. Dinheiro movimentado e receita de jogo são grandezas
distintas e não se reconciliam entre si — tentar amarrar uma na outra produz número sem
significado.

---

## `agg_qualidade_lote`

**Pergunta que responde**: quanto do lote foi descartado, por qual motivo, e onde está o que foi
descartado.

**Grão**: uma linha por `lote_data` × `entidade` × `motivo`.

| Coluna | Definição |
|---|---|
| `qtd_recebidos` | Linhas que chegaram a RAW para aquela entidade no lote |
| `qtd_aceitos` | Linhas que chegaram ao modelo limpo |
| `qtd_rejeitados` | Linhas em quarentena **por aquele motivo** |
| `qtd_rejeitados_distintos` | Registros distintos em quarentena na entidade e lote |
| `taxa_rejeicao` | `qtd_rejeitados_distintos / qtd_recebidos` |

**Por que duas colunas de rejeitados**: um registro pode violar várias regras ao mesmo tempo — uma
duplicata que também tem campo nulo, por exemplo. Ele aparece em **várias linhas de motivo**, mas
conta **uma vez** no total. Somar `qtd_rejeitados` por motivo daria um número maior que a
realidade; o invariante usa a coluna distinta.

**Invariante garantido por teste**: por lote e entidade,
`qtd_recebidos = qtd_aceitos + qtd_rejeitados_distintos`. Se essa igualdade quebrar, algum
registro se perdeu entre a carga e a quarentena, e o pipeline falha.

**O motivo `sem_rejeicao`**: entidade e lote sem nenhum descarte aparecem com esse motivo e
contagem zero, em vez de sumirem da tabela. Um lote limpo precisa ser visível — ausência de linha
seria indistinguível de lote não processado.

**A taxa não bloqueia**: nenhum valor de `taxa_rejeicao`, nem 100%, interrompe a execução. Ela
reporta. O que bloqueia o pipeline são os testes estruturais — unicidade, não-nulidade,
integridade referencial e sanidade de negócio. Foi decisão explícita: os defeitos são injetados de
propósito, então uma taxa alta é comportamento esperado, não anomalia de infraestrutura.

### Catálogo de motivos

| Motivo | Regra violada |
|---|---|
| `duplicata` | Perdeu a disputa por marcador de atualização mais recente |
| `nulo_obrigatorio` | Campo obrigatório nulo ou vazio |
| `valor_nao_positivo` | Valor menor ou igual a zero |
| `data_posterior_ao_evento` | Data da aposta posterior à data do evento |
| `apostador_inexistente` | Referencia apostador que não existe na camada limpa |
| `evento_inexistente` | Referencia evento que não existe na camada limpa |
| `premio_inconsistente` | Prêmio diferente de zero em status que não é `ganha` |
| `status_invalido` | Valor fora do conjunto fechado do domínio |
| `sem_rejeicao` | Sentinela: entidade e lote sem nenhum descarte |

**Não é rejeição**: prêmio **maior** que o valor apostado. É o comportamento normal de uma aposta
ganha com odd alta.

---

## Rastreabilidade

Todo registro descartado fica em `BETS.STAGING.QUA_REGISTROS_REJEITADOS`, com o conteúdo original
preservado em `VARIANT`, o arquivo e o número da linha de origem, o lote e todos os motivos
aplicáveis. O caminho de uma métrica suspeita até a linha exata do CSV é sempre possível.

## Ressalva conhecida

Se uma execução falhar entre a construção dos fatos e a dos agregados, `fct_apostas` pode ficar
momentaneamente à frente dos quatro `agg_*`. Os agregados continuam consistentes entre si e
refletem o lote anterior; a reexecução resolve. O motivo pelo qual essa lacuna foi aceita, e a
alternativa que foi rejeitada, estão em
`specs/002-betting-analytics-platform/research.md`, decisão D3.
