# Feature Specification: Plataforma Analítica de Apostas Esportivas

**Feature Branch**: `002-betting-analytics-platform`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Plataforma de dados analítica para uma casa de apostas esportivas fictícia. A empresa precisa acompanhar diariamente a saúde do negócio (receita, volume apostado e engajamento dos apostadores), mas os dados operacionais chegam com problemas de qualidade e sem padronização. Um gerador de dados sintéticos produz lotes diários simulando o sistema transacional, com apostadores, eventos esportivos, apostas e transações financeiras, e injeta de propósito duplicatas, nulos em campos obrigatórios, valores de aposta negativos ou zerados e datas de aposta posteriores à data do evento."

## Clarifications

### Session 2026-09-11

- Q: Quais status de aposta devem entrar no cálculo do GGR diário? → A: Apenas apostas resolvidas
  (`ganha` e `perdida`), mais uma coluna separada de exposição pendente — valor apostado em
  apostas ainda abertas — que não se mistura com o GGR.
- Q: Quando uma aposta que estava pendente é resolvida num lote posterior, o GGR do dia original
  deve ser recalculado? → A: Sim. A aposta é guardada por identificador com o último status
  conhecido, e as métricas de toda data afetada são recalculadas; o GGR de um dia passado muda
  quando uma pendente resolve.
- Q: Quando o mesmo identificador de aposta aparece duas vezes dentro de um único lote com conteúdo
  diferente, qual das versões deve sobreviver? → A: A de marcador de atualização mais recente — o
  gerador passa a emitir esse marcador por registro — com empate resolvido por ordenação
  determinística de todos os campos. A cópia descartada vai para a quarentena.
- Q: O pipeline deve falhar quando a taxa de registros rejeitados de um lote passar de um limite, ou
  deve sempre processar o que sobrou e apenas reportar a taxa? → A: Nunca falha por taxa. O lote é
  processado com o que sobrou e a taxa fica registrada no resumo de qualidade; apenas testes
  estruturais — unicidade, não-nulidade, integridade referencial e sanidade de negócio — bloqueiam a
  execução.
- Q: Quando uma execução falha no meio, que estado deve ficar armazenado? → A: A camada bruta
  sempre retém o lote recebido, por ser imutável e auditável; as camadas de dados limpos e de
  métricas são tudo ou nada, de modo que nenhuma métrica parcial fique visível. A correção é seguida
  de reexecução do lote inteiro, que é segura por idempotência.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - GGR diário por esporte (Priority: P1)

O analista de negócio abre a tabela de métricas no início do dia e vê, para cada dia e cada
esporte, o total apostado, o total pago em prêmios e o GGR resultante. Ele consegue responder
"quanto a casa ganhou ontem, e em quais esportes" sem abrir nenhuma planilha nem recalcular nada
à mão.

**Why this priority**: GGR é a métrica de receita da casa e a razão de existir da plataforma.
Entregue sozinha, ela já responde à pergunta mais cara do negócio e constitui um MVP defensável:
sem ela, nenhuma outra métrica justifica o pipeline.

**Independent Test**: Gerar um lote diário, processá-lo e consultar a tabela de GGR. O teste passa
se o GGR de cada par (dia, esporte) for igual a `total apostado − prêmios pagos` calculado
independentemente sobre as apostas válidas daquele lote.

**Acceptance Scenarios**:

1. **Given** um lote diário contendo apostas válidas de mais de um esporte, **When** o lote é
   processado, **Then** a tabela de métricas apresenta uma linha por dia e esporte com total
   apostado, prêmios pagos e GGR, e o GGR é a diferença entre os dois.
2. **Given** um lote em que todos os prêmios pagos de um esporte superam o total apostado nesse
   esporte, **When** o lote é processado, **Then** o GGR daquele esporte é apresentado como valor
   negativo, sem erro e sem truncamento para zero.
3. **Given** um lote contendo apostas canceladas e apostas pendentes, **When** o lote é
   processado, **Then** nenhuma das duas entra no total apostado, nos prêmios pagos ou no GGR, e a
   documentação da métrica declara essa exclusão.
4. **Given** um lote com apostas pendentes, **When** o lote é processado, **Then** o valor apostado
   dessas apostas aparece na coluna de exposição pendente do mesmo par (dia, esporte), separado do
   GGR, e a soma das duas colunas nunca é apresentada como receita.
5. **Given** o mesmo lote já processado anteriormente, **When** ele é processado de novo,
   **Then** os valores de GGR permanecem exatamente os mesmos.
6. **Given** uma aposta de um dia anterior que estava pendente, **When** um lote posterior a
   entrega com status `ganha` ou `perdida`, **Then** o GGR e a exposição pendente da data original
   da aposta são recalculados para refletir o novo status, e a aposta aparece uma única vez.

---

### User Story 2 - Rastreabilidade da qualidade por lote (Priority: P2)

O engenheiro de dados consulta, para qualquer lote processado, quantos registros foram recebidos,
quantos foram aceitos e quantos foram descartados — quebrado por motivo de descarte — e consegue
abrir os registros descartados para inspecionar exatamente o que veio errado.

**Why this priority**: É o que torna os números da US1 confiáveis. Sem essa visibilidade, uma
queda de GGR é indistinguível de um lote com mais lixo do que o normal, e a exigência de que
registro inválido seja rastreável em vez de apagado fica sem evidência. Também é o que se mostra
numa apresentação ao vivo para provar que o pipeline filtra de verdade.

**Independent Test**: Gerar um lote com proporções conhecidas de cada defeito injetado, processá-lo
e verificar que a contagem de rejeitados por motivo bate exatamente com o que foi injetado, e que
cada registro rejeitado pode ser consultado com o lote e o motivo associados.

**Acceptance Scenarios**:

1. **Given** um lote com 5% de apostas duplicadas, 3% com nulos obrigatórios, 2% com valor
   negativo ou zero e 2% com data de aposta posterior ao evento, **When** o lote é processado,
   **Then** o resumo de qualidade do lote reporta as contagens por motivo coincidindo com as
   proporções injetadas.
2. **Given** qualquer lote processado, **When** o engenheiro soma aceitos e rejeitados, **Then** o
   total confere exatamente com o número de registros recebidos naquele lote.
3. **Given** um registro descartado, **When** o engenheiro o consulta, **Then** ele encontra o
   conteúdo original do registro, o identificador do lote e o motivo do descarte.
4. **Given** um registro que viola mais de uma regra ao mesmo tempo, **When** o lote é processado,
   **Then** ele é contado uma única vez no total de rejeitados e todos os motivos aplicáveis ficam
   registrados.

---

### User Story 3 - Engajamento diário dos apostadores (Priority: P3)

O analista acompanha, por dia, o volume total apostado, o ticket médio por aposta e a quantidade
de apostadores ativos, e percebe variações relevantes de um dia para o outro.

**Why this priority**: Complementa a leitura de receita da US1 com a leitura de atividade, mas
depende dos mesmos dados já limpos. Entregue sozinha não responde à pergunta de receita, por isso
vem depois.

**Independent Test**: Processar um lote e verificar que volume apostado, ticket médio e apostadores
ativos daquele dia correspondem, respectivamente, à soma dos valores apostados válidos, à média
desses valores e à contagem distinta de apostadores com ao menos uma aposta válida.

**Acceptance Scenarios**:

1. **Given** um lote diário processado, **When** o analista consulta as métricas de engajamento,
   **Then** encontra uma linha por dia com volume apostado, ticket médio e apostadores ativos.
2. **Given** um apostador com várias apostas válidas no mesmo dia, **When** as métricas são
   calculadas, **Then** ele é contado uma única vez como apostador ativo naquele dia.
3. **Given** um dia sem nenhuma aposta válida, **When** as métricas são calculadas, **Then** o dia
   aparece com volume zero, apostadores ativos zero e ticket médio vazio — nunca uma divisão por
   zero nem um dia ausente sem explicação.

---

### User Story 4 - Movimentação financeira diária (Priority: P4)

O time financeiro compara, dia a dia, quanto entrou em depósitos e quanto saiu em saques, e vê o
saldo líquido do movimento.

**Why this priority**: É uma visão de caixa independente das apostas, valiosa mas não necessária
para validar a tese central da plataforma. Pode ser cortada sem comprometer as histórias
anteriores.

**Independent Test**: Processar um lote com depósitos e saques conhecidos e verificar que os
totais diários e o líquido correspondem à soma independente de cada tipo de transação válida.

**Acceptance Scenarios**:

1. **Given** um lote com depósitos e saques válidos, **When** o lote é processado, **Then** a
   tabela financeira apresenta, por dia, total depositado, total sacado e o líquido
   (depósitos − saques).
2. **Given** um dia com saques maiores que depósitos, **When** o lote é processado, **Then** o
   líquido é apresentado como valor negativo, sem erro.

---

### Edge Cases

- **Lote vazio**: o lote é processado com sucesso, registra zero recebidos e zero rejeitados, e as
  tabelas de métricas permanecem consistentes — não é tratado como falha.
- **Lote 100% inválido**: a execução termina com sucesso, nenhum registro chega às métricas e o
  resumo de qualidade reporta 100% de rejeição com a quebra por motivo. A taxa não interrompe o
  pipeline (FR-016a); a anomalia fica visível no resumo de qualidade e no log da execução.
- **Aposta órfã**: aposta que referencia apostador ou evento inexistente é descartada como violação
  de integridade referencial e fica rastreável com esse motivo.
- **Duplicata parcial**: dois registros com o mesmo identificador de aposta mas conteúdo diferente
  são resolvidos pelo marcador de atualização mais recente; se o marcador também empatar, decide a
  ordenação determinística de todos os campos. A ordem de leitura nunca influencia o resultado, e a
  versão perdedora fica na quarentena.
- **Prêmio maior que o valor apostado**: é comportamento normal de aposta ganha com odd alta e MUST
  ser aceito; só a inconsistência estrutural (prêmio pago em aposta perdida ou cancelada) é
  descartada.
- **Aposta pendente que se resolve depois**: o mesmo identificador de aposta reaparece em lote
  posterior com status final. A versão canônica é substituída, as métricas da data original da
  aposta são recalculadas — saindo da exposição pendente e entrando no GGR — e a aposta nunca é
  contada duas vezes.
- **Reprocessamento com conteúdo diferente**: reprocessar a mesma data com um lote de conteúdo
  diferente substitui o lote anterior por completo, nunca soma os dois.
- **Falha no meio da execução**: o lote bruto permanece armazenado, as tabelas de dados limpos e de
  métricas continuam exibindo o estado anterior à execução, e a reexecução do lote inteiro após a
  correção leva ao estado correto sem limpeza manual.
- **Fronteira de dia**: apostas próximas da virada do dia são atribuídas a um único dia segundo uma
  regra explícita e documentada, sem cair em dois dias nem em nenhum.
- **Valor apostado zerado versus nulo**: ambos são inválidos, mas com motivos de descarte distintos
  e contabilizados separadamente.

## Requirements *(mandatory)*

### Functional Requirements

**Geração e recebimento de lotes**

- **FR-001**: O sistema MUST gerar lotes diários sintéticos contendo apostadores, eventos
  esportivos, apostas e transações financeiras, a partir de uma semente fixa que torne o conteúdo
  do lote reproduzível.
- **FR-002**: O sistema MUST injetar, em proporções configuráveis por defeito, os quatro problemas
  de qualidade previstos: apostas duplicadas, nulos em campos obrigatórios, valores de aposta
  negativos ou zerados, e datas de aposta posteriores à data do evento.
- **FR-003**: O sistema MUST identificar cada lote de forma única pela sua data lógica, e essa data
  MUST ser um parâmetro explícito da execução, nunca a data corrente implícita.
- **FR-004**: O sistema MUST preservar os registros exatamente como recebidos, antes de qualquer
  limpeza, e MUST manter esse conteúdo consultável para auditoria.

**Validação e quarentena**

- **FR-005**: O sistema MUST manter exatamente uma ocorrência por identificador de aposta. Quando o
  mesmo identificador aparece mais de uma vez no lote, sobrevive a ocorrência de marcador de
  atualização mais recente; em caso de empate no marcador, o desempate MUST ser feito por ordenação
  determinística de todos os campos do registro, de modo que o resultado nunca dependa da ordem de
  leitura. Toda ocorrência descartada MUST ir para a quarentena com o motivo "duplicata".
- **FR-005a**: Cada registro gerado MUST carregar um marcador de atualização que permita ordená-lo
  frente a outras versões do mesmo identificador.
- **FR-006**: O sistema MUST rejeitar todo registro com nulo em campo obrigatório, e a lista de
  campos obrigatórios por entidade MUST estar declarada na especificação dos dados.
- **FR-007**: O sistema MUST rejeitar toda aposta com valor apostado menor ou igual a zero.
- **FR-008**: O sistema MUST rejeitar toda aposta cuja data seja posterior à data do evento
  correspondente.
- **FR-009**: O sistema MUST rejeitar toda aposta que referencie apostador ou evento inexistente.
- **FR-010**: O sistema MUST registrar cada registro rejeitado em uma área de quarentena consultável
  contendo o conteúdo original, o identificador do lote, o momento do descarte e todos os motivos
  aplicáveis. Apagar registro inválido sem rastro é PROIBIDO.
- **FR-011**: O sistema MUST impedir que qualquer registro rejeitado seja considerado no cálculo de
  qualquer métrica de negócio.
- **FR-012**: O sistema MUST padronizar tipos, nomes de campos e domínios de valores (por exemplo, o
  conjunto fechado de status de aposta) antes de calcular qualquer métrica.

**Métricas de negócio**

- **FR-013**: O sistema MUST disponibilizar, por dia e por esporte, o total apostado, o total de
  prêmios pagos e o GGR (total apostado menos prêmios pagos), considerando apenas apostas válidas
  com status `ganha` ou `perdida`. Apostas `cancelada` e `pendente` MUST ficar fora dessas três
  colunas.
- **FR-013a**: O sistema MUST disponibilizar, na mesma granularidade de dia e esporte, uma coluna
  de exposição pendente contendo o valor apostado em apostas válidas com status `pendente`. Essa
  coluna MUST ser independente do GGR e nunca somada a ele.
- **FR-014**: O sistema MUST disponibilizar, por dia, o volume total apostado, o ticket médio por
  aposta e a quantidade de apostadores ativos distintos.
- **FR-015**: O sistema MUST disponibilizar, por dia, o total depositado, o total sacado e o líquido
  entre os dois.
- **FR-016**: O sistema MUST disponibilizar, por lote, o total de registros recebidos, aceitos e
  rejeitados, com a contagem e a taxa de rejeição quebradas por motivo e por entidade.
- **FR-016a**: A taxa de rejeição é informativa: nenhum valor de taxa, incluindo 100%, MUST
  interromper a execução. Um lote é sempre processado com os registros que sobraram após a
  validação.
- **FR-017**: Cada métrica publicada MUST declarar, em documentação versionada, o que inclui e o
  que exclui — em particular o tratamento dado a apostas canceladas e pendentes.

**Execução do pipeline**

- **FR-018**: Uma única execução da orquestração MUST gerar, carregar, validar, transformar e testar
  o lote, sem nenhum passo manual intermediário.
- **FR-019**: Reprocessar o mesmo lote MUST produzir exatamente o mesmo estado final, sem duplicar
  nenhum registro em nenhuma etapa.
- **FR-019a**: O sistema MUST manter uma única versão canônica de cada aposta, identificada pelo seu
  identificador, refletindo o último status conhecido. Um lote que traga o mesmo identificador com
  status atualizado MUST substituir a versão anterior, nunca criar uma segunda linha. A escolha da
  versão vencedora usa o mesmo marcador de atualização de FR-005, de modo que a regra de "vence o
  mais recente" seja uma só dentro e entre lotes.
- **FR-019b**: Quando um lote atualiza o status de apostas de datas anteriores, o sistema MUST
  recalcular as métricas de todas as datas afetadas, de modo que GGR e exposição pendente daquelas
  datas passem a refletir o estado canônico atual.
- **FR-020**: Falha de qualquer teste estrutural de dados — unicidade de chave, não-nulidade,
  integridade referencial e sanidade de negócio das métricas — MUST interromper a execução e impedir
  a escrita na etapa seguinte. Alertar sem bloquear é PROIBIDO para esses testes. A taxa de rejeição
  não é um desses testes (FR-016a).
- **FR-020a**: Quando uma execução falha, o conteúdo bruto do lote já recebido MUST permanecer
  disponível para auditoria, enquanto as tabelas de dados limpos e de métricas MUST ficar no estado
  anterior à execução — nenhum resultado parcial do lote em falha pode ficar visível.
- **FR-020b**: Após a correção do problema, reexecutar o lote inteiro MUST ser suficiente para levar
  o pipeline ao estado correto, sem necessidade de retomada parcial nem de limpeza manual.
- **FR-021**: Cada execução MUST registrar data lógica do lote, contagens de registros lidos,
  aceitos, rejeitados e escritos por etapa, duração e resultado dos testes.

### Key Entities *(include if feature involves data)*

**Entidades de origem (produzidas pelo gerador)**

- **Apostador**: pessoa fictícia titular de uma conta. Identificador, data de criação da conta e
  estado de residência. Nenhum dado pessoal real.
- **Evento Esportivo**: partida ou disputa passível de aposta. Identificador, esporte, campeonato,
  times envolvidos e data do evento.
- **Aposta**: intenção de apostar de um apostador sobre um evento. Identificador, apostador, evento,
  data da aposta, valor apostado, odd, status (ganha, perdida, pendente ou cancelada), prêmio pago e
  marcador de atualização. É a entidade central das métricas de receita, e o marcador de atualização
  é o que define qual versão do registro é canônica (FR-005, FR-019a).
- **Transação Financeira**: movimento de dinheiro entre o apostador e a casa. Identificador,
  apostador, data, tipo (depósito ou saque) e valor.
- **Lote Diário**: conjunto de registros das quatro entidades acima referente a uma data lógica. É a
  unidade de processamento e de reprocessamento.

**Entidades derivadas (produzidas pela plataforma)**

- **Registro Rejeitado**: cópia de um registro de origem que violou ao menos uma regra de qualidade,
  acompanhada do lote, do momento e dos motivos do descarte.
- **GGR Diário por Esporte**: total apostado, prêmios pagos, GGR e exposição pendente, por data e
  esporte. As três primeiras colunas consideram apenas apostas resolvidas; a exposição pendente é
  uma leitura separada e nunca é somada ao GGR.
- **Engajamento Diário**: volume apostado, ticket médio e apostadores ativos, por data.
- **Movimentação Financeira Diária**: total depositado, total sacado e líquido, por data.
- **Resumo de Qualidade do Lote**: recebidos, aceitos e rejeitados por lote, com quebra por motivo e
  por entidade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um lote diário novo é processado de ponta a ponta com um único comando, sem nenhuma
  intervenção manual entre as etapas.
- **SC-002**: Processar o mesmo lote duas vezes seguidas produz contagens e valores idênticos em
  todas as tabelas de métricas — variação zero em 100% dos campos comparados.
- **SC-003**: 100% dos registros que violam alguma regra de qualidade são impedidos de influenciar
  qualquer métrica de negócio; a contagem de registros inválidos presentes nas tabelas de métricas
  é zero.
- **SC-004**: 100% dos registros descartados permanecem consultáveis com lote e motivo associados;
  nenhum registro é perdido sem rastro.
- **SC-005**: Para todo lote, recebidos = aceitos + rejeitados, sem diferença.
- **SC-006**: O analista responde "qual foi o GGR de ontem, por esporte" com uma única consulta às
  tabelas de métricas, sem cálculo manual e sem cruzar planilhas.
- **SC-007**: A demonstração ao vivo — gerar um lote, processá-lo e ler as métricas resultantes —
  cabe em 10 minutos, incluindo a exibição do resumo de qualidade.
- **SC-008**: Um terceiro, partindo de máquina limpa e seguindo apenas a documentação, chega a
  métricas populadas sem precisar de suporte do autor.
- **SC-009**: Um lote com qualquer taxa de rejeição, inclusive 100%, é processado até o fim sem
  falhar, e a taxa fica registrada no resumo de qualidade daquele lote.
- **SC-010**: Depois de uma execução que falhou, a contagem de métricas parciais visíveis referentes
  àquele lote é zero, e o conteúdo bruto do lote continua consultável para auditoria.

## Assumptions

Estas decisões foram tomadas na ausência de definição explícita e podem ser revistas sem
reestruturar a especificação:

- **Data de referência das métricas diárias**: as métricas de aposta são agregadas pela data da
  aposta, não pela data do evento nem pela data do lote. As métricas financeiras são agregadas pela
  data da transação.
- **Apostador ativo**: apostador com ao menos uma aposta válida na data, contado de forma distinta.
- **Prêmio pago em aposta perdida ou cancelada**: valor diferente de zero nesses status é
  inconsistência estrutural e leva ao descarte do registro.
- **Chegada tardia e correção**: um lote é a verdade completa dos registros que ele entrega —
  reprocessar uma data substitui integralmente o conteúdo bruto daquele lote — mas um lote pode
  trazer atualização de status de apostas de datas anteriores. Nesse caso vale o estado canônico
  mais recente por identificador de aposta (FR-019a) e as datas afetadas são recalculadas
  (FR-019b). Em consequência, o GGR de um dia passado não é imutável: ele é sempre a melhor
  leitura disponível daquele dia.
- **Compatibilidade com o Princípio V da constituição**: o princípio exige que falha de teste de
  dados bloqueie o pipeline, e isso continua valendo integralmente para os testes estruturais
  (FR-020). A taxa de rejeição não é um teste — é uma métrica observada de um comportamento
  esperado, já que os defeitos são injetados de propósito — por isso reportá-la sem bloquear não
  configura "portão que só avisa".
- **Volume dos lotes**: ordem de dezenas de milhares de registros por lote — o suficiente para que
  as métricas sejam interessantes e para que o processamento caiba no tempo de uma demo.
- **Dados sintéticos**: nenhum dado real de apostador é usado, conforme o Princípio VI da
  constituição do projeto; toda apresentação das métricas declara que os números são sintéticos.
- **Sem branch dedicada**: nenhum hook de criação de branch está configurado neste projeto, então o
  identificador `002-betting-analytics-platform` nomeia a feature, não necessariamente um branch
  git.

## Out of Scope

- Ingestão ou processamento de dados em tempo real — o ciclo é diário, por lote.
- Qualquer componente de machine learning, incluindo previsão, detecção de anomalia por modelo ou
  segmentação automática.
- Dashboard de visualização: opcional, entra apenas se houver tempo após todos os critérios de
  sucesso acima estarem atendidos. Nenhum critério de sucesso depende dele.
- Correção automática de registros inválidos: o escopo é descartar com rastreabilidade, não
  reparar.
- Integração com qualquer sistema transacional real da casa de apostas.
