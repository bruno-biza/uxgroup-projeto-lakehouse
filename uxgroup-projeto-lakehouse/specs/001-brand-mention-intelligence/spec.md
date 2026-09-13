# Feature Specification: Brand Mention Intelligence — Share of Voice de Marcas de Apostas

**Feature Branch**: `001-brand-mention-intelligence`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "Plataforma analítica de inteligência competitiva de marca para uma
operadora de apostas esportivas e cassino online licenciada no Brasil. Mede share of voice de 3
marcas próprias (Reals, BetGO, Bingo) contra 4 concorrentes (KTO, Esportiva, Brazino777,
Superbet) na cobertura jornalística global, com identificação de marca de precisão medida e
publicada, a partir de fonte pública e gratuita."

## Clarifications

### Session 2026-09-08

- Q: Quais notícias entram na contagem da "cobertura da categoria de apostas" que serve de
  denominador do share of voice? → A: União de duas origens — a taxonomia temática fornecida pela
  própria fonte e uma lista de termos do setor versionada no repositório — com a origem da
  inclusão registrada em cada conteúdo.
- Q: O share of voice de referência é global, restrito ao Brasil, ou os dois? → A: Duas métricas
  distintas e nomeadas (`share_of_voice_global` e `share_of_voice_brasil`), publicadas lado a lado
  e ambas declaradas no dicionário de dados.
- Q: As personas Analista de Mídia e Compliance entram na entrega, e com que prioridade? → A:
  Espaço em branco de mídia entra como SHOULD (História 8, P8, à frente das demais SHOULD por ser
  derivada de dados que as MUST já produzem); a visão agregada de Compliance entra como COULD, na
  fila de corte, preservada apenas a marcação neutra das menções exigida pelo Princípio XII.
- Q: Menções identificadas com confiança baixa entram na contagem das métricas de negócio? → A:
  Não. Vale um piso de confiança único, explícito e igual para todas as marcas, calibrado contra o
  conjunto de avaliação; menções abaixo dele são preservadas mas excluídas das métricas, e o
  volume descartado é reportado junto de cada métrica.
- Q: O que caracteriza um dia anômalo para uma marca, de forma testável? → A: Desvio robusto — dia
  cujo volume se afasta da mediana da linha de base da própria marca em mais de N desvios
  absolutos medianos (MAD), com N documentado e configurável.

### Session 2026-09-09 — conflitos com a realidade das fontes

Ambos originados da verificação da documentação oficial durante o planejamento
(ver [research.md](./research.md) §4 e §10).

- Q: FR-023 exigia coincidência exata entre menções listadas e volume da série, mas a fonte tem
  teto de 250 registros por chamada e **não tem paginação**. → A: FR-023 reescrito para
  reconciliação medida e publicada, com FR-023a (subdivisão do período quando truncado) e FR-023b
  (sinalização de exaustivo vs. truncado). Cenário 2 da História 3 ajustado.
- Q: SC-006 exigia pipeline completo em menos de 20 minutos, incompatível com a carga inicial de
  centenas de requisições em série. → A: SC-006 passa a valer para o ciclo diário incremental;
  SC-006a cobre a carga inicial sem SLA de 20 minutos, com o tempo efetivo registrado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identificação de marca auditável com precisão publicada (Priority: P1)

Qualquer usuário que receba um número desta plataforma precisa saber que as menções contadas
foram efetivamente validadas como referentes à marca, e não como coincidência de texto. O sistema
mantém um conjunto de avaliação rotulado manualmente e publica precisão e revocação do
identificador de marca como número, na documentação, por versão do identificador.

**Why this priority**: Vários nomes monitorados colidem com vocabulário comum — "Reals" com a
moeda e com clubes de futebol, "Bingo" com o jogo, "Esportiva" com a expressão "aposta esportiva"
e com o nome de um veículo do setor, "BetGO" e "KTO" com termos e siglas genéricas. Toda métrica
das demais histórias é derivada da contagem de menções; se a identificação não for medida, todas
elas publicam número errado com aparência de número certo. Esta é a única história que, sozinha,
já entrega um ativo defensável, e nenhuma outra pode ser publicada sem ela.

**Independent Test**: Executar o identificador contra o conjunto de avaliação rotulado e obter
precisão e revocação por marca e no agregado, sem depender de nenhuma métrica de negócio estar
construída. Entrega valor por si: um identificador de marca com qualidade conhecida e um conjunto
de avaliação reutilizável.

**Acceptance Scenarios**:

1. **Given** um conjunto de avaliação com no mínimo 300 menções candidatas rotuladas manualmente
   como marca ou não-marca, cobrindo obrigatoriamente Reals, Bingo e Esportiva, **When** o
   identificador vigente é executado sobre ele, **Then** o sistema publica precisão e revocação
   por marca e no agregado, com a versão do identificador e a data da medição.
2. **Given** um texto que contém "reais" no sentido de moeda e nenhum sinal da marca Reals,
   **When** o identificador o processa, **Then** nenhuma menção da marca Reals é contabilizada.
3. **Given** um conteúdo que referencia o domínio oficial canônico de uma marca, **When** o
   identificador o processa, **Then** a menção é classificada como daquela marca com nível de
   confiança alto e o método de identificação registrado é a âncora de domínio.
4. **Given** uma nova versão do identificador cuja precisão em qualquer marca é inferior à da
   versão anterior registrada, **When** o pipeline é executado, **Then** o pipeline falha e a nova
   versão não é promovida.
5. **Given** uma métrica de negócio cuja precisão do identificador que a alimenta não está
   documentada, **When** um usuário tenta consultá-la, **Then** a métrica não é publicada.
6. **Given** uma menção candidata cuja confiança de identificação está abaixo do piso vigente,
   **When** as métricas do período são calculadas, **Then** ela não é contabilizada, permanece
   consultável marcada como abaixo do piso, e seu volume é reportado junto da métrica.
7. **Given** o piso de confiança vigente, **When** a precisão é medida contra o conjunto de
   avaliação, **Then** a medição considera exatamente a mesma população que alimenta as métricas
   de negócio, isto é, apenas as menções acima do piso.

---

### User Story 2 - Share of voice diário por marca em 3 meses (Priority: P2)

O Analista de Marca abre a série temporal diária das últimas 12 semanas e compara a fatia de
cobertura da categoria que cita cada uma das 7 marcas, para saber se as marcas próprias estão
ganhando ou perdendo espaço frente às concorrentes.

**Why this priority**: É a pergunta de negócio central e a primeira que a operadora hoje não sabe
responder. Depende da História 1 para ser publicável, mas é a razão pela qual a plataforma existe.

**Independent Test**: Consultar a série diária de menções e de share de voz para as 7 marcas em
uma janela de 3 meses e verificar que cada ponto tem numerador, denominador e definição de
categoria explícitos.

**Acceptance Scenarios**:

1. **Given** a janela de monitoramento ativo de 3 meses processada, **When** o Analista de Marca
   consulta a série diária, **Then** existe um valor de volume absoluto e os dois valores de share
   de voz — global e Brasil — para cada uma das 7 marcas em cada dia da janela, inclusive dias com
   valor zero.
2. **Given** uma marca com forte cobertura internacional, **When** o analista compara os dois
   recortes, **Then** vê a posição competitiva da marca no recorte global e no recorte Brasil sem
   que um contamine o outro.
3. **Given** um dia da janela, **When** o analista consulta qualquer um dos dois shares de voz,
   **Then** a métrica expõe o numerador (menções da marca no recorte), o denominador (cobertura da
   categoria no mesmo dia e no mesmo recorte) e a regra que delimita a categoria.
4. **Given** uma métrica normalizada pelo volume global de cobertura, **When** ela é exibida,
   **Then** a normalização está explícita no nome e na descrição da métrica.
5. **Given** qualquer métrica de share de voz, **When** ela é exibida, **Then** vem acompanhada da
   declaração de que mede exposição na imprensa monitorada pela fonte — não alcance publicitário,
   não sentimento do consumidor, não receita — e da ressalva de que a cobertura da fonte é ampla
   mas não exaustiva.

---

### User Story 3 - Investigação de um pico de cobertura no dia (Priority: P3)

A Assessoria de Imprensa detecta um pico de menções e precisa, no mesmo dia, abrir a lista das
menções que compõem aquele volume para descobrir o que aconteceu e reagir a tempo.

**Why this priority**: É o uso operacional de maior urgência temporal e o que converte o número
agregado em ação. Sem o detalhe da menção, o pico é um número sem enredo.

**Independent Test**: Escolher uma marca e uma data e obter a lista completa de menções daquele
dia, com veículo, título, idioma, país de publicação e endereço do conteúdo.

**Acceptance Scenarios**:

1. **Given** uma marca e uma data dentro da janela ativa, **When** a assessoria consulta as
   menções daquele dia, **Then** recebe a lista com veículo, título, idioma, país de publicação,
   endereço do conteúdo, indicador de tom, método de identificação e nível de confiança de cada
   menção.
2. **Given** a lista de menções de um dia, **When** ela é somada, **Then** o total é reconciliado
   com o volume absoluto daquele dia na série temporal da História 2, e a lista informa se é
   exaustiva ou truncada, com a diferença explícita quando houver.
3. **Given** uma menção exibida, **When** o usuário verifica seu indicador de tom, **Then** o
   indicador está rotulado como sinal automatizado e aproximado fornecido pela fonte, e não como
   análise de sentimento validada.

---

### User Story 4 - Distribuição de cobertura por veículo, país e idioma (Priority: P4)

O Analista de Marca precisa saber de onde vem a cobertura de cada marca: quais veículos publicam,
em que países e em que idiomas, para entender se a exposição é doméstica ou internacional.

**Why this priority**: Qualifica o volume da História 2 — mesmo volume vindo de veículos e países
diferentes significa posicionamentos competitivos diferentes.

**Independent Test**: Consultar, para uma marca e um período, o ranking de veículos e as
distribuições por país e por idioma de publicação, e conferir que os totais fecham com o volume
absoluto do mesmo período.

**Acceptance Scenarios**:

1. **Given** uma marca e um período, **When** o analista consulta a distribuição por veículo,
   **Then** recebe a contagem de menções por veículo ordenada, e a soma das contagens é igual ao
   volume absoluto da marca no período.
2. **Given** uma marca e um período, **When** o analista consulta a distribuição por país e por
   idioma de publicação, **Then** recebe as duas distribuições com a mesma propriedade de
   fechamento de totais.
3. **Given** um veículo presente na distribuição, **When** o analista o inspeciona, **Then** vê
   domínio, nome e país do veículo, e se ele cobre a categoria de apostas.

---

### User Story 5 - Reprocessamento idempotente e regra de contagem de republicação (Priority: P5)

O Engenheiro de Dados reprocessa um intervalo de datas após corrigir uma regra e precisa obter
contagem idêntica, sem duplicidade, e precisa que o mesmo conteúdo republicado por vários portais
siga uma regra de contagem documentada e testada.

**Why this priority**: Sem isso, toda correção exige limpeza manual e nenhum número histórico é
confiável após um reprocessamento. É pré-requisito operacional para as demais histórias
sobreviverem a qualquer correção.

**Independent Test**: Executar o mesmo intervalo duas vezes com a mesma data lógica e comparar
contagem de linhas e conteúdo das camadas de consumo.

**Acceptance Scenarios**:

1. **Given** um intervalo já processado, **When** ele é reprocessado com a mesma data lógica,
   **Then** as camadas de consumo apresentam contagem de linhas e conteúdo idênticos, sem linhas
   duplicadas.
2. **Given** o mesmo conteúdo republicado por vários portais distintos, **When** o pipeline o
   processa, **Then** ele é contabilizado como uma menção por veículo, conforme a regra documentada
   e coberta por teste.
3. **Given** o mesmo conteúdo coletado duas vezes do mesmo veículo, **When** o pipeline o processa,
   **Then** ele é contabilizado uma única vez.
4. **Given** uma marca nova a ser monitorada, **When** ela é adicionada ao cadastro de marcas e ao
   conjunto de avaliação, **Then** ela passa a ser monitorada sem alteração na lógica do pipeline.

---

### User Story 6 - Confiança antes da reunião: frescor e resultado dos testes (Priority: P6)

Qualquer usuário, antes de levar um número a uma reunião, precisa ver quando a tabela que o
originou foi atualizada, qual data lógica ela cobre e se passou nos testes.

**Why this priority**: Um número sem procedência não é levado a uma reunião. Converte a disciplina
interna de qualidade em sinal visível para o usuário de negócio.

**Independent Test**: Consultar o painel de estado de cada tabela de consumo e verificar que
exibe data da última atualização, data lógica processada e resultado da última execução de testes.

**Acceptance Scenarios**:

1. **Given** qualquer tabela de consumo, **When** o usuário a consulta, **Then** vê a data e hora
   da última atualização bem-sucedida, a data lógica processada e o resultado dos testes.
2. **Given** uma execução em que qualquer teste de qualidade falhou, **When** o pipeline roda,
   **Then** ele é interrompido, a camada seguinte não é escrita e a falha fica registrada e
   visível ao usuário.
3. **Given** uma tabela cuja atualização está fora do SLA de frescor calibrado pelo atraso real de
   publicação da fonte, **When** o usuário a consulta, **Then** o atraso é sinalizado
   explicitamente.

---

### User Story 7 - Linha de base histórica de 12 meses (Priority: P7)

O Analista de Marca precisa saber se o volume da janela recente é pico ou é normal, comparando-o
com uma linha de base histórica de pelo menos 12 meses da própria marca.

**Why this priority**: Sem base histórica, "aumento de 40%" é uma frase sem referência. Habilita a
detecção de anomalia da História 9.

**Independent Test**: Consultar, para cada marca, a distribuição histórica de volume diário sobre
pelo menos 12 meses e obter os parâmetros de referência usados para julgar normalidade.

**Acceptance Scenarios**:

1. **Given** o histórico carregado, **When** o analista consulta a linha de base de uma marca,
   **Then** ela cobre pelo menos 12 meses de granularidade diária.
2. **Given** um volume observado na janela ativa, **When** comparado à linha de base da própria
   marca, **Then** o sistema informa a posição do valor frente à distribuição histórica.

---

### User Story 8 - Espaço em branco de mídia (Priority: P8)

O Analista de Mídia precisa da lista nominal de veículos que cobrem a categoria de apostas com
regularidade e que nunca citaram nenhuma das marcas próprias no período, para priorizar
relacionamento com imprensa.

**Why this priority**: É a única história que sai do diagnóstico e entrega uma lista acionável no
dia seguinte. O custo é baixo porque deriva de dados que as histórias MUST já produzem — o
cadastro de veículos com a marcação de quem cobre a categoria (FR-019) e a distribuição de menções
por veículo (FR-018). Por isso vem antes das demais SHOULD na ordem de corte.

**Independent Test**: Consultar, para um período, a lista de veículos que publicaram sobre a
categoria acima de um limiar mínimo de conteúdos e que não registram menção a Reals, BetGO ou
Bingo, e conferir manualmente uma amostra dessa lista.

**Acceptance Scenarios**:

1. **Given** um período e o cadastro de veículos, **When** o Analista de Mídia consulta o espaço
   em branco, **Then** recebe a lista de veículos que cobriram a categoria no período e não
   registram nenhuma menção às marcas próprias, com domínio, nome, país e volume de conteúdos da
   categoria publicados.
2. **Given** um veículo que citou uma marca própria uma única vez no período, **When** a lista é
   gerada, **Then** ele não aparece no espaço em branco, e a lista distingue "nunca citou" de
   "citou pouco".
3. **Given** um veículo com volume de cobertura da categoria abaixo do limiar mínimo, **When** a
   lista é gerada, **Then** ele é excluído, para que a lista não se encha de veículos que
   publicaram um único conteúdo sobre o assunto.
4. **Given** a lista do espaço em branco, **When** ela é exibida, **Then** vem acompanhada da
   ressalva de que ausência de menção na fonte não prova ausência de publicação — apenas que a
   fonte, cuja cobertura não é exaustiva, não registrou nenhuma.

---

### User Story 9 - Indicador de tom da cobertura ao longo do tempo (Priority: P9)

A Assessoria de Imprensa acompanha a evolução do indicador de tom da cobertura por marca, para
distinguir crescimento de exposição favorável de crescimento por crise regulatória.

**Why this priority**: Distingue volume bom de volume ruim — informação que muda a reação da
assessoria. Fica abaixo do volume porque é sinal aproximado e depende da série já existir.

**Independent Test**: Consultar a série do indicador de tom por marca ao longo do tempo e
verificar que toda exibição carrega a ressalva de sinal automatizado e aproximado.

**Acceptance Scenarios**:

1. **Given** um período e uma marca, **When** o usuário consulta o indicador de tom, **Then**
   recebe a série agregada acompanhada da ressalva de que é sinal automatizado e aproximado
   fornecido pela fonte.
2. **Given** menções sem indicador de tom disponível na fonte, **When** a série é agregada,
   **Then** elas são excluídas do cálculo e a quantidade excluída é informada.
3. **Given** qualquer exibição do indicador de tom, **When** ela é rotulada, **Then** não usa o
   termo "análise de sentimento" nem apresenta o indicador como validado.

---

### User Story 10 - Detecção automática de anomalia de volume (Priority: P10)

O Analista de Inteligência Competitiva quer ser avisado quando uma marca — própria ou concorrente
— concentra cobertura anômala frente à linha de base dela mesma, e não frente às outras marcas.

**Why this priority**: Transforma monitoramento passivo em alerta. Depende diretamente da linha de
base da História 7.

**Independent Test**: Injetar um dia de volume atipicamente alto para uma marca no histórico e
verificar que ele é sinalizado como anomalia com magnitude de desvio, enquanto dias normais não
são.

**Acceptance Scenarios**:

1. **Given** um dia cujo volume de uma marca excede a mediana da sua linha de base em mais de N
   desvios absolutos medianos, **When** a detecção roda, **Then** uma anomalia é registrada com
   marca, data, magnitude do desvio em MAD e status de revisão.
2. **Given** um dia dentro do limiar de N MAD, **When** a detecção roda, **Then** nenhuma anomalia
   é registrada para aquela marca naquele dia.
3. **Given** uma marca com volume estruturalmente maior que as demais, **When** a detecção roda,
   **Then** ela não é sinalizada por esse motivo, porque a comparação é contra a própria linha de
   base.
4. **Given** uma marca cuja linha de base tem dispersão nula (MAD igual a zero), **When** a
   detecção roda, **Then** o caso é tratado pela regra específica de dispersão nula e a marca não
   tem todo dia não nulo sinalizado como anomalia.
5. **Given** uma anomalia registrada, **When** o analista a revisa, **Then** pode alterar seu
   status de revisão e o histórico da anomalia é preservado.

---

### User Story 11 - Hipótese de causa da anomalia (Priority: P11)

Cada anomalia detectada vem acompanhada de uma hipótese de causa construída a partir das notícias
daquele dia, explicitamente rotulada como hipótese não verificada.

**Why this priority**: Reduz o tempo entre alerta e entendimento. Fica no fim das SHOULD porque
carrega o maior risco de afirmação indevida e é o primeiro candidato a corte por prazo.

**Independent Test**: Para uma anomalia conhecida, gerar a hipótese e verificar que ela cita as
menções que a sustentam e vem rotulada como não verificada.

**Acceptance Scenarios**:

1. **Given** uma anomalia registrada, **When** o analista a consulta, **Then** recebe uma hipótese
   de causa derivada das menções daquele dia, com as menções que a sustentam referenciadas.
2. **Given** qualquer hipótese de causa exibida, **When** ela é apresentada, **Then** está rotulada
   como hipótese não verificada e não afirma relação causal.
3. **Given** o componente automatizado que gera a hipótese estar indisponível ou sem cota, **When**
   a anomalia é consultada, **Then** o sistema apresenta a hipótese produzida pelo modo de
   fallback determinístico baseado em regras, com a mesma rotulagem.

---

### Edge Cases

- **Colisão de nome com veículo de imprensa**: um artigo publicado pelo veículo "Esportiva" não é,
  por si só, uma menção à marca Esportiva. Menção pelo autor e menção à marca precisam ser
  distinguidas.
- **Marca com forte presença fora do Brasil**: marcas do portfólio monitorado têm operação
  internacional e podem gerar volume alto de cobertura estrangeira sem qualquer relação com o
  mercado brasileiro. Os dois recortes de share de voz (global e Brasil) tornam essa diferença
  visível em vez de diluí-la num total único.
- **Recorte Brasil com amostra pequena**: em dias de baixa cobertura, o recorte Brasil pode ter
  volume tão pequeno que uma variação percentual grande não significa nada. O volume absoluto que
  sustenta o recorte é exibido junto do percentual para que o usuário julgue a leitura.
- **Conteúdo sem país de publicação identificado**: menções cujo país a fonte não informa entram
  no recorte global e ficam fora do recorte Brasil; a quantidade nessa situação é reportada para
  que a diferença entre os dois denominadores seja explicável.
- **Artigo que cita várias marcas**: um mesmo conteúdo pode citar 3 marcas e conta como menção
  para cada uma; o denominador da categoria conta o conteúdo uma vez, de modo que a soma dos
  shares de voz pode exceder 100%. A regra precisa estar documentada onde a métrica é exibida.
- **Republicação sindicalizada**: o mesmo texto publicado por 40 portais é 40 menções (uma por
  veículo) e não 1 nem 40 vezes o mesmo veículo. A regra é documentada e testada.
- **Dia sem nenhuma menção de uma marca**: a série apresenta zero explícito, não lacuna, para que
  a queda não seja confundida com falha de coleta.
- **Dia sem cobertura da categoria** (denominador zero): o share de voz é indefinido, não zero, e é
  exibido como indefinido.
- **Menção apenas no endereço do conteúdo**: o nome da marca aparecendo somente na URL exige
  tratamento explícito de sinal, com confiança registrada, e é julgada pelo piso como qualquer
  outra.
- **Volume descartado maior que o contabilizado**: se as menções abaixo do piso superarem as
  contabilizadas em um período, o fato é reportado explicitamente — é sinal de que o piso está mal
  calibrado ou de que a marca é ambígua demais para a regra vigente, e não deve passar despercebido.
- **Fonte indisponível ou com atraso**: a coleta falha, o registro de falha fica visível, e as
  camadas seguintes continuam servindo o último estado válido sem apresentá-lo como atual.
- **Conteúdo removido ou alterado retroativamente pelo veículo**: a menção já registrada na zona
  bruta permanece; a plataforma não reescreve o passado.
- **Marca nova ou renomeada durante a janela**: o cadastro de marcas é versionado e a série
  histórica indica a partir de quando a marca passou a ser monitorada.
- **Nome de marca em idioma que não usa alfabeto latino**: menções que a fonte registre em outros
  alfabetos podem escapar às variações grafadas conhecidas; a revocação medida na História 1 é o
  instrumento que expõe essa perda.

## Requirements *(mandatory)*

### Functional Requirements

#### Cadastro e identificação de marca

- **FR-001**: O sistema MUST manter um cadastro versionado das marcas monitoradas contendo
  identificador, nome, domínio oficial canônico, variações grafadas conhecidas, papel (própria ou
  concorrente), razão social e identificadores regulatórios públicos quando disponíveis, e nível de
  risco de ambiguidade do nome.
- **FR-002**: O sistema MUST tratar o domínio oficial canônico como âncora de identificação de
  alta confiança, registrando a âncora como método de identificação quando ela for o sinal usado.
- **FR-003**: O sistema MUST desambiguar menções de nomes que colidem com vocabulário comum ou com
  o vocabulário do setor, cobrindo obrigatoriamente Reals, Bingo, Esportiva, BetGO e KTO.
- **FR-004**: Toda menção identificada MUST registrar o método que identificou a marca e o nível
  de confiança da identificação.
- **FR-004a**: O sistema MUST aplicar um piso de confiança único, explícito e igual para todas as
  marcas monitoradas: apenas menções com confiança igual ou superior ao piso entram nas métricas
  de negócio. Um piso diferente por marca é proibido, porque tornaria os denominadores do share de
  voz não comparáveis entre marcas.
- **FR-004b**: O piso de confiança MUST ser calibrado contra o conjunto de avaliação de forma a
  atender à meta de precisão, MUST estar declarado no dicionário de dados, e sua alteração MUST
  ser tratada como mudança de definição de métrica, com data de vigência registrada.
- **FR-004c**: Menções abaixo do piso MUST ser preservadas e permanecer consultáveis, marcadas
  como abaixo do piso, e MUST NOT ser contabilizadas em nenhuma métrica de negócio.
- **FR-004d**: Toda métrica de negócio MUST reportar, junto do seu valor, o volume de menções
  candidatas descartadas por confiança abaixo do piso no mesmo período.
- **FR-005**: O sistema MUST manter um conjunto de avaliação rotulado manualmente e versionado no
  repositório, com no mínimo 300 menções candidatas classificadas como marca ou não-marca,
  cobrindo obrigatoriamente Reals, Bingo e Esportiva, e registrando para cada rótulo o motivo,
  quem rotulou e quando.
- **FR-006**: O sistema MUST medir precisão e revocação de cada versão do identificador contra o
  conjunto de avaliação, por marca e no agregado, e publicar os números na documentação com a
  versão do identificador e a data da medição.
- **FR-007**: O sistema MUST bloquear a publicação de qualquer métrica de negócio cuja precisão do
  identificador que a alimenta não esteja documentada.
- **FR-008**: O sistema MUST reprovar a promoção de uma versão do identificador cuja precisão seja
  inferior à da versão anterior em qualquer marca monitorada.

#### Coleta e preservação

- **FR-009**: O sistema MUST preservar toda resposta da fonte como recebida, antes de qualquer
  interpretação, junto dos metadados de coleta: momento, endpoint, parâmetros, status, tentativas,
  e bytes estimados e efetivamente varridos quando aplicável.
- **FR-010**: O sistema MUST reconstruir todas as camadas derivadas exclusivamente a partir do
  material preservado, sem nenhuma chamada externa.
- **FR-011**: O sistema MUST coletar exclusivamente de interfaces públicas oficiais e documentadas,
  identificando o projeto e um contato em toda requisição.
- **FR-012**: O sistema MUST NOT coletar, armazenar ou inferir qualquer dado pessoal.

#### Corpus, métricas e share of voice

- **FR-013**: O sistema MUST delimitar o universo "cobertura jornalística da categoria de apostas"
  pela união de duas origens — a taxonomia temática fornecida pela própria fonte e uma lista de
  termos do setor versionada no repositório — e MUST registrar, em cada conteúdo incluído no
  denominador, qual das duas origens o incluiu (ou ambas).
- **FR-013a**: A lista de termos do setor MUST ser versionada no repositório, e toda alteração
  nela MUST ser tratada como mudança de definição de métrica: a data de vigência fica registrada e
  as séries que a usam como denominador indicam qual versão da lista produziu cada ponto.
- **FR-013b**: O sistema MUST publicar, por período, a composição do denominador segundo a origem
  da inclusão (apenas taxonomia, apenas lista de termos, ambas), para que a sensibilidade do share
  de voz à regra de categoria seja verificável.
- **FR-014**: O sistema MUST calcular, por marca e por dia, o volume absoluto de menções e o share
  de voz sobre a cobertura da categoria no mesmo dia, expondo numerador, denominador e regra de
  categoria.
- **FR-015**: O sistema MUST documentar, onde a métrica for exibida, que um conteúdo citando
  várias marcas conta como menção para cada uma enquanto o denominador o conta uma vez, e que por
  isso a soma dos shares de voz pode exceder 100%.
- **FR-016**: O sistema MUST cobrir uma janela de monitoramento ativo de 3 meses com granularidade
  diária para todas as marcas monitoradas, representando dias sem menção como zero explícito.
- **FR-017**: O sistema MUST manter linha de base histórica de pelo menos 12 meses por marca para
  julgamento de normalidade e sazonalidade.
- **FR-018**: O sistema MUST apresentar a distribuição de menções por veículo, por país de
  publicação e por idioma de publicação, com totais que fecham com o volume absoluto do período.
- **FR-019**: O sistema MUST manter um cadastro de veículos com domínio, nome, país e indicação de
  se o veículo cobre a categoria de apostas.
- **FR-020**: O sistema MUST publicar o share de voz em dois recortes geográficos distintos e
  nomeados — `share_of_voice_global` (toda a cobertura da categoria) e `share_of_voice_brasil`
  (cobertura cujo país de publicação é o Brasil) — cada um com seu próprio numerador e
  denominador, e ambos declarados no dicionário de dados.
- **FR-020a**: O sistema MUST NOT exibir uma métrica de share de voz sem o recorte geográfico
  explícito no nome da métrica; nome genérico sem recorte é proibido.
- **FR-020b**: O sistema MUST informar, junto do recorte Brasil, o volume absoluto de menções que
  o sustenta, para que o usuário possa julgar se a amostra do dia é pequena demais para leitura de
  variação percentual.
- **FR-021**: O sistema MUST expor o indicador de tom fornecido pela fonte rotulado como sinal
  automatizado e aproximado, e MUST NOT apresentá-lo como análise de sentimento validada.

#### Consumo e transparência metodológica

- **FR-022**: Usuários MUST conseguir listar as menções de uma marca em uma data, com veículo,
  título, idioma, país de publicação, endereço do conteúdo, indicador de tom, método de
  identificação e nível de confiança.
- **FR-023**: O sistema MUST reconciliar, para cada marca e dia, a contagem de menções listadas
  em detalhe com o volume absoluto da série agregada, e MUST publicar a diferença junto do
  resultado quando ela existir. A fonte impõe teto de 250 registros por chamada de listagem, sem
  paginação, de modo que a enumeração exaustiva nem sempre é possível; a exigência é que a
  diferença seja medida e visível, nunca silenciosa.
- **FR-023a**: Quando a listagem de um dia atingir o teto da fonte, o sistema MUST subdividir o
  período em janelas menores e reconsultar, até que a listagem deixe de ser truncada ou até o
  limite de requisições da execução.
- **FR-023b**: O sistema MUST sinalizar, em toda listagem de menções, se ela é exaustiva ou
  truncada, e qual a cobertura estimada frente ao volume da série.
- **FR-024**: O sistema MUST expor, para cada tabela de consumo, a data e hora da última
  atualização bem-sucedida, a data lógica processada e o resultado da última execução de testes.
- **FR-025**: O sistema MUST manter um dicionário de dados em que cada métrica declare o que mede,
  o que não mede, os limites de cobertura da fonte e, quando aplicável, a normalização aplicada.
- **FR-026**: O sistema MUST apresentar relações entre séries como correlação e MUST NOT
  apresentá-las como causa.

#### Anomalias

- **FR-027**: O sistema MUST sinalizar como anomalia o dia cujo volume de menções de uma marca se
  afasta da mediana da linha de base da própria marca em mais de N desvios absolutos medianos
  (MAD), com N documentado e configurável, registrando marca, data, magnitude do desvio em MAD e
  status de revisão.
- **FR-027a**: A comparação MUST ser sempre contra a linha de base da própria marca, e MUST NOT
  usar o volume das demais marcas como referência, para que uma marca estruturalmente maior não
  seja sinalizada por seu porte.
- **FR-027b**: O sistema MUST tratar explicitamente o caso de dispersão nula na linha de base
  (MAD igual a zero), típico de marcas de volume muito baixo, sem sinalizar todo dia não nulo como
  anomalia.
- **FR-027c**: O valor de N e a janela da linha de base MUST estar documentados junto da lista de
  anomalias, e sua alteração MUST ser tratada como mudança de definição de métrica.
- **FR-028**: O sistema MUST associar a cada anomalia uma hipótese de causa derivada das menções
  do dia, referenciando as menções que a sustentam e rotulada como hipótese não verificada.
- **FR-029**: O sistema MUST dispor de um modo de fallback determinístico, baseado em regras, para
  a geração de hipótese, usado nos testes e quando o componente automatizado estiver indisponível.

#### Operação e qualidade

- **FR-030**: O sistema MUST produzir estado final idêntico ao reexecutar qualquer etapa com a
  mesma data lógica, sem duplicar linhas, recebendo a data lógica como parâmetro explícito.
- **FR-031**: O sistema MUST aplicar uma regra documentada e testada de contagem de republicação:
  o mesmo conteúdo publicado por vários veículos conta como uma menção por veículo, e o mesmo
  conteúdo coletado mais de uma vez do mesmo veículo conta uma única vez.
- **FR-032**: O sistema MUST interromper o processamento quando qualquer teste de qualidade
  falhar, sem escrever a camada seguinte.
- **FR-033**: O sistema MUST verificar o frescor de cada tabela de consumo contra um SLA calibrado
  pelo atraso real de publicação da fonte, obtido da documentação oficial da fonte.
- **FR-034**: O sistema MUST permitir incluir uma nova marca monitorada alterando apenas o cadastro
  de marcas e o conjunto de avaliação, sem alteração na lógica de processamento.
- **FR-035**: O sistema MUST registrar, por execução, a data lógica, linhas lidas e escritas,
  custo estimado e efetivo de consulta à fonte quando aplicável, duração, resultado dos testes e
  falhas de chamada externa.
- **FR-036**: O sistema MUST tratar menções sobre regulação, jogo compulsivo e integridade
  esportiva como categoria analítica de acompanhamento, com neutralidade, e MUST NOT usá-las como
  insumo de segmentação comercial.

#### Espaço em branco de mídia

- **FR-037**: O sistema MUST identificar, para um período, os veículos que publicaram sobre a
  categoria de apostas e não registram nenhuma menção às marcas próprias, apresentando domínio,
  nome, país e volume de conteúdos da categoria publicados por veículo.
- **FR-038**: O sistema MUST aplicar um limiar mínimo de conteúdos da categoria por veículo no
  período para inclusão no espaço em branco, com o limiar documentado junto da lista.
- **FR-039**: O sistema MUST distinguir "nunca citou" de "citou pouco" na apresentação do espaço
  em branco, e MUST declarar que ausência de menção na fonte não prova ausência de publicação,
  dado que a cobertura da fonte não é exaustiva.

### Key Entities

- **Marca**: identificador, nome, domínio oficial canônico, variações grafadas conhecidas, papel
  (própria ou concorrente), razão social e identificadores regulatórios públicos quando
  disponíveis, nível de risco de ambiguidade do nome, e período em que passou a ser monitorada.
- **Menção**: marca identificada, data e hora, veículo, país e idioma de publicação, título,
  endereço do conteúdo, indicador de tom, método que identificou a marca, nível de confiança e
  indicação de se está acima ou abaixo do piso de confiança vigente. Relaciona-se com Marca e com
  Veículo.
- **Item de avaliação rotulado**: menção candidata, rótulo humano (marca ou não-marca), motivo do
  rótulo, quem rotulou e quando. É a base contra a qual as Métricas de identificação são medidas.
- **Métricas de identificação**: versão do identificador, precisão, revocação, marca a que se
  referem (ou agregado), e data da medição.
- **Veículo**: domínio, nome, país, e se cobre a categoria de apostas.
- **Anomalia**: marca, data, magnitude do desvio em desvios absolutos medianos frente à linha de
  base da própria marca, valor de N e janela da linha de base vigentes na detecção, hipótese de
  causa, menções que a sustentam e status de revisão.
- **Metadados de coleta**: momento, endpoint, parâmetros, status, tentativas, bytes estimados e
  varridos quando aplicável, e resposta bruta preservada.
- **Cobertura da categoria**: o conjunto de conteúdos jornalísticos que compõem o denominador do
  share de voz em cada dia. Cada conteúdo registra a origem que o incluiu (taxonomia temática da
  fonte, lista de termos do setor, ou ambas) e a versão vigente da lista de termos no momento da
  inclusão.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A janela de monitoramento ativo cobre 3 meses completos com granularidade diária
  para as 7 marcas monitoradas, sem dias faltantes.
- **SC-002**: A linha de base histórica cobre pelo menos 12 meses por marca.
- **SC-003**: A camada bruta contém no mínimo 10 milhões de linhas, provenientes do corpus de
  cobertura da categoria e não apenas das menções das 7 marcas.
- **SC-004**: O conjunto de avaliação contém pelo menos 300 menções rotuladas manualmente, com
  cobertura obrigatória de Reals, Bingo e Esportiva.
- **SC-005**: A precisão do identificador de marca está medida e publicada, com no mínimo 85% para
  cada marca de nome ambíguo (Reals, Bingo, Esportiva, BetGO, KTO).
- **SC-006**: O **ciclo diário incremental** executa de ponta a ponta em menos de 20 minutos,
  incluindo coleta, transformação, testes e avaliação de precisão.
- **SC-006a**: A **carga inicial** (janela ativa de 3 meses e linha de base histórica) roda em
  processo separado, sem SLA de 20 minutos, e o tempo efetivo é registrado na documentação. O
  limite de requisições da fonte torna as duas cargas incomparáveis: 7 requisições por dia contra
  centenas na carga inicial.
- **SC-007**: 100% dos modelos de consumo possuem teste automatizado e todos passam.
- **SC-008**: Um teste automatizado comprova a reconstrução completa de todas as camadas com a
  rede desabilitada.
- **SC-009**: Um teste automatizado comprova que nenhuma consulta à fonte pública executa sem
  filtro de partição e sem teto de bytes declarado.
- **SC-010**: Um teste automatizado comprova que reprocessar o mesmo intervalo com a mesma data
  lógica produz contagem idêntica, sem duplicidade.
- **SC-011**: Um avaliador externo, sem apoio do autor, sobe o projeto seguindo apenas o README em
  menos de 30 minutos.
- **SC-012**: A demonstração completa cabe em 10 minutos cronometrados.
- **SC-013**: 100% das métricas publicadas declaram o que medem, o que não medem e os limites de
  cobertura da fonte.
- **SC-014**: 100% das métricas publicadas reportam o volume de menções descartadas por confiança
  abaixo do piso no período, e o piso vigente está declarado no dicionário de dados.
- **SC-015**: A lista do espaço em branco de mídia é gerada para o período de monitoramento ativo
  e uma amostra de 20 veículos dela é conferida manualmente, com o resultado da conferência
  registrado.
- **SC-016**: Um teste automatizado injeta um dia sintético de volume atípico e comprova que ele é
  sinalizado como anomalia, e que dias dentro do limiar de N MAD não são.

## Escopo Excluído

- Dados internos reais da operadora: apostas, valores, dados de clientes ou qualquer dado pessoal.
- Raspagem de sites de concorrentes ou de qualquer fonte sem interface pública oficial e
  documentada.
- Análise de redes sociais fechadas ou de fontes que exijam contrato pago.
- Treinamento de modelo de aprendizado de máquina em produção.
- Aplicação web de front-end própria. Um painel visual navegável permanece classificado como
  COULD e será cortado antes de qualquer teste ou documentação.

**Classificados COULD — fila de corte, nesta ordem** (Princípio XIV: corta-se COULD e depois
SHOULD; nunca teste, documentação ou roteiro de demo):

1. Cruzamento de picos de menção com a atenção pública sobre propriedades esportivas
   patrocinadas — primeiro a sair.
2. Painel visual navegável.
3. Métrica agregada de risco reputacional para Compliance e Assuntos Regulatórios: série
   dedicada de cobertura sobre regulação, jogo compulsivo e integridade esportiva por marca e por
   período. A marcação dessas menções como categoria analítica neutra permanece obrigatória
   (FR-036) por exigência do Princípio XII da constituição; o que é COULD é a métrica agregada e
   a visão dedicada da persona.
- Atribuição de receita, alcance publicitário ou intenção de compra a partir de menções.

## Assumptions

- **Fonte única e pública**: a cobertura jornalística vem de um conjunto de dados público e
  gratuito de âmbito global, cuja coleta e cujo custo estão sujeitos às travas do Princípio I da
  constituição. Nenhuma fonte paga é assumida.
- **Cobertura não exaustiva**: a fonte monitora um subconjunto amplo, porém não exaustivo, dos
  veículos brasileiros. Toda métrica declara essa limitação; a plataforma não afirma cobertura
  total do mercado.
- **Menção como unidade**: a unidade de contagem é a menção por veículo, e não o artigo único nem
  o leitor alcançado.
- **Janela e histórico**: os 3 meses de monitoramento ativo estão contidos nos 12 meses ou mais de
  linha de base, de modo que a janela recente possa ser comparada ao seu próprio histórico.
- **Meta de precisão**: a meta de 85% aplica-se às marcas de nome ambíguo; para as marcas de nome
  não ambíguo (Brazino777, Superbet) espera-se precisão igual ou superior, mas o corte formal de
  reprovação é a regressão entre versões, não um piso absoluto.
- **Indicador de tom herdado**: o indicador de tom é consumido como fornecido pela fonte; a
  plataforma não constrói nem valida classificador de sentimento próprio.
- **Identificadores regulatórios**: razão social e identificadores regulatórios públicos das
  marcas são preenchidos quando disponíveis em fonte pública oficial; sua ausência não bloqueia o
  monitoramento da marca.
- **Consumo analítico, não aplicação**: o consumo se dá por consulta às tabelas do modelo
  analítico e pela documentação publicada; nenhuma interface própria é construída.
- **Volume de linhas**: o mínimo de 10 milhões de linhas refere-se ao corpus da categoria
  preservado na camada bruta, dimensionado para que o denominador do share de voz seja
  estatisticamente significativo.
- **Prazo**: a entrega está sujeita ao Princípio XIV da constituição — 7 dias corridos, com corte
  de COULD e depois de SHOULD, nunca de teste, documentação ou roteiro de demo.
