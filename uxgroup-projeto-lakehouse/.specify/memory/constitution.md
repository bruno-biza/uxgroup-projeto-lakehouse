<!--
SYNC IMPACT REPORT
==================
Versão: 1.0.0 → 2.0.0
Tipo de bump: MAJOR — mudança de escopo do projeto (de inteligência de menções de marca sobre
fonte pública externa para plataforma de dados de apostas esportivas com dados sintéticos no
Snowflake). Princípios foram removidos e redefinidos de forma incompatível com a versão anterior.

Princípios removidos (não se aplicam ao novo escopo):
- II. Cidadania de API — o projeto não consome mais nenhuma API externa; os dados são gerados
  localmente.
- IV. Precisão de Identificação de Marca é Métrica, não Opinião — não há mais identificação de
  marca em texto.
- XIII. IA com Rastreabilidade — não há mais componente de IA no escopo.

Princípios redefinidos (renomeados / reescritos com regra incompatível):
- I. Custo Zero com Trava Técnica → I. Custo Zero (trava de bytes no BigQuery substituída por
  conta trial do Snowflake e ferramentas open-source locais).
- III. Imutabilidade da Zona Bruta → absorvido por III. Arquitetura Medallion no Snowflake
  (camada RAW) e por II. Pipeline Ponta a Ponta Reproduzível.
- V. Arquitetura Lakehouse em Camadas → III. Arquitetura Medallion no Snowflake
  (landing/bronze/silver/gold → RAW/STAGING/MARTS).
- VI. Qualidade de Dados como Portão → V. Qualidade como Bloqueio (portões agora em STAGING e
  MARTS).
- VII. Honestidade Metodológica + XII. Ética e Conformidade Setorial → VI. Dados 100% Sintéticos
  e Reprodutíveis.
- VIII. Python-First e Legibilidade → VII. Python para Geração e Ingestão, SQL para Transformação.
- IX. Idempotência e Reprocessamento → IV. Idempotência.
- X. Tudo como Código → absorvido por II. Pipeline Ponta a Ponta Reproduzível e X. Documentação
  é Entregável.
- XI. Observabilidade → rebaixado a requisito mínimo na seção Restrições Técnicas Adicionais
  (Princípio IX: simplicidade antes de sofisticação).
- XIV. Escopo Blindado pelo Prazo → IX. Simplicidade Antes de Sofisticação; o prazo passou de 7
  para 3 dias e migrou para a seção de Restrições Técnicas Adicionais.

Princípios adicionados:
- II. Pipeline Ponta a Ponta Reproduzível
- VIII. Segredos Fora do Código (elevado de restrição técnica a princípio)
- X. Documentação é Entregável

Seções: as três seções de apoio (Restrições Técnicas Adicionais, Fluxo de Desenvolvimento e
Portões de Qualidade, Governance) foram mantidas e reescritas para o novo escopo. Nenhuma seção
adicionada ou removida.

TODOs resolvidos por remoção de escopo:
- TODO(SLA_FRESHNESS) — o SLA dependia do atraso de publicação de uma fonte externa que não
  existe mais.
- TODO(CONTATO_USER_AGENT) — não há mais cliente HTTP externo.

TODOs diferidos: nenhum.
-->

# UX Group Lakehouse Constitution

Plataforma de dados para uma empresa de apostas esportivas (bets), construída sobre dados
sintéticos e entregue como projeto de processo seletivo, com prazo de 3 dias e apresentação ao
vivo. A entrega é o pipeline completo funcionando de ponta a ponta, reproduzível por um terceiro
em máquina limpa.

## Core Principles

### I. Custo Zero (NÃO-NEGOCIÁVEL)

**Regra**: O projeto MUST rodar inteiramente sobre a conta trial gratuita do Snowflake e
ferramentas open-source executadas localmente. Nenhum recurso pago pode ser contratado ou
consumido.

**Justificativa**: O projeto é avaliado pelo raciocínio de engenharia, não pelo orçamento. Custo
zero também garante que o avaliador consiga reproduzir a entrega com a própria conta trial, sem
barreira financeira.

**Obrigações**:
- Warehouse: exclusivamente a conta trial do Snowflake. Nenhum upgrade de plano, nenhum serviço
  cobrado por uso.
- Tudo que não for o warehouse MUST rodar localmente a partir de ferramentas open-source; serviço
  gerenciado de terceiros com cobrança é PROIBIDO.
- O warehouse Snowflake MUST usar o menor tamanho disponível e ter auto-suspend configurado em
  código, para não consumir créditos ocioso.
- Nenhum recurso criado fora do que a infraestrutura versionada declara; recurso criado à mão na
  interface web não existe para efeito de reprodução.

**Verificação**: o README lista todas as dependências externas do projeto, e cada uma é a conta
trial do Snowflake ou uma ferramenta open-source local — item fora dessa lista reprova a revisão.
A configuração do warehouse versionada declara tamanho mínimo e auto-suspend.

### II. Pipeline Ponta a Ponta Reproduzível (NÃO-NEGOCIÁVEL)

**Regra**: Uma única execução da orquestração MUST gerar, carregar, transformar e testar os
dados, sem nenhum passo manual intermediário.

**Justificativa**: O entregável é o fluxo completo, não as partes. Um pipeline que exige
intervenção manual entre etapas não é reproduzível por um avaliador e não sobrevive a uma
apresentação ao vivo.

**Obrigações**:
- Um único comando dispara a orquestração, e ela executa geração → ingestão (RAW) → transformação
  (STAGING → MARTS) → testes de dados, nessa ordem.
- Passo manual entre etapas é PROIBIDO. Qualquer preparação necessária (criação de schemas,
  warehouse, roles) MUST estar no mesmo comando ou em um comando de bootstrap único e
  documentado.
- Ambiente e infraestrutura versionados no repositório, aplicáveis do zero por um terceiro.
- Falha em qualquer etapa MUST interromper a execução com código de saída diferente de zero; a
  etapa seguinte não roda.

**Verificação**: em máquina limpa, com apenas as credenciais no `.env` e os pré-requisitos do
README instalados, a sequência documentada de comandos leva do repositório vazio a MARTS populado
e testado, sem passo não documentado. Se exigir intervenção manual, está reprovado.

### III. Arquitetura Medallion no Snowflake

**Regra**: O dado MUST atravessar exatamente três camadas no Snowflake — RAW, STAGING e MARTS —
cada uma lendo apenas da camada imediatamente anterior.

**Justificativa**: Camadas com fronteira nítida tornam o erro localizável e a linhagem legível;
salto de camada transforma o pipeline num grafo opaco em que nenhuma correção é segura.

**Obrigações**:
- **RAW**: o dado como foi gerado, sem nenhuma alteração — sem limpeza, sem renomeação de coluna,
  sem cast, sem filtro, sem deduplicação. RAW é append-only e nunca editada linha a linha.
- **STAGING**: dado limpo e tipado — tipos explícitos, nomes padronizados, deduplicação e regras
  de conformação. Nenhuma métrica de negócio aqui.
- **MARTS**: métricas e agregações de negócio, modeladas para consumo analítico.
- Salto de camada é PROIBIDO: MARTS não lê RAW, e nada fora da ingestão escreve em RAW.

**Verificação**: a linhagem gerada a partir do código é inspecionada e qualquer aresta que pule
uma camada reprova o build. Inspeção de RAW confirma que as colunas correspondem ao que o gerador
emitiu, sem transformação aplicada.

### IV. Idempotência (NÃO-NEGOCIÁVEL)

**Regra**: Reexecutar o mesmo lote MUST produzir o mesmo estado final. Duplicação de dados por
reexecução é defeito, nunca comportamento aceitável.

**Justificativa**: Sem idempotência, toda falha parcial exige limpeza manual do warehouse — o que
quebra o Princípio II e é inviável num prazo de 3 dias, além de ser risco direto na demo ao vivo.

**Obrigações**:
- Nenhuma etapa usa data corrente implícita: a data lógica do lote vem sempre do orquestrador como
  parâmetro explícito.
- Toda carga em RAW é idempotente por identificador de lote — recarregar o mesmo lote substitui ou
  ignora, nunca acumula.
- Modelos incrementais têm chave única declarada e estratégia de merge documentada.

**Verificação**: teste que executa o mesmo lote duas vezes e afirma contagem de linhas idêntica em
RAW, STAGING e MARTS. Busca por `now()`, `today()`, `current_date` ou `CURRENT_TIMESTAMP` em
código de pipeline retorna vazio ou apenas usos de auditoria explicitamente justificados.

### V. Qualidade como Bloqueio (NÃO-NEGOCIÁVEL)

**Regra**: Testes de dados MUST existir em STAGING e em MARTS, e falha de teste MUST interromper o
pipeline — nunca apenas alertar.

**Justificativa**: Um portão que só avisa é um portão aberto; dado ruim que avança de camada
contamina as métricas de negócio e as conclusões da apresentação silenciosamente.

**Obrigações**:
- Todo modelo de STAGING e MARTS com teste de unicidade e não-nulidade na chave primária e
  integridade referencial nas chaves estrangeiras.
- MARTS: além dos testes de chave, ao menos um teste de sanidade de negócio por métrica (faixa de
  valores aceitável, sinal esperado, ou conciliação de totais contra a camada anterior).
- Falha de teste MUST abortar a execução com código de saída diferente de zero e sem escrita na
  camada seguinte.
- Modelo sem teste é PROIBIDO: modelo novo sem teste correspondente reprova a revisão.

**Verificação**: execução do pipeline com um teste deliberadamente falho termina com código de
saída diferente de zero e sem materializar a camada seguinte. Inventário automático confirma que
todo modelo de STAGING e MARTS aparece na suíte de testes.

### VI. Dados 100% Sintéticos e Reprodutíveis (NÃO-NEGOCIÁVEL)

**Regra**: Todos os dados MUST ser sintéticos, gerados por código com seed fixa. Nenhum dado
pessoal real, de nenhuma origem, em nenhuma camada.

**Justificativa**: O setor de apostas é regulado e socialmente sensível, e um projeto de processo
seletivo não tem base legal para tratar dado real de apostador. Seed fixa garante que o avaliador
veja exatamente os mesmos números descritos na documentação.

**Obrigações**:
- A seed é declarada em configuração versionada; a mesma seed MUST produzir exatamente o mesmo
  conjunto de dados.
- Nenhum dado pessoal real — identificado, pseudonimizado, inferido ou derivado. Nenhuma carga de
  arquivo externo com dado de pessoa real.
- Toda apresentação dos dados (README, dashboards, roteiro de demo) MUST declarar explicitamente
  que os dados são sintéticos; apresentar número sintético como real é PROIBIDO.
- O gerador cobre os cenários de negócio que as métricas de MARTS pretendem medir, incluindo os
  casos de borda usados nos testes.

**Verificação**: duas execuções do gerador com a mesma seed produzem saída com checksum idêntico.
Revisão de esquema confirma ausência de coluna com dado pessoal real em RAW, STAGING e MARTS. O
README e o roteiro de demo contêm a declaração de dados sintéticos.

### VII. Python para Geração e Ingestão, SQL para Transformação

**Regra**: Python é a linguagem padrão para geração de dados, ingestão e utilitários; SQL é a
linguagem das transformações analíticas entre camadas.

**Justificativa**: Uma divisão clara de linguagem reduz o custo de leitura por um avaliador e
mantém a transformação onde ela é mais legível e testável — dentro do warehouse.

**Obrigações**:
- Transformação analítica em SQL. Transformação de dados feita em Python fora da ingestão é
  PROIBIDA sem justificativa escrita.
- Type hints em toda função pública; docstring de módulo explicando o porquê, não o quê.
- Regras de negócio não óbvias comentadas em português.

**Verificação**: linter e checador de tipos rodam e reprovam função pública sem anotação ou módulo
sem docstring. Revisão recusa lógica de transformação analítica implementada em Python sem
justificativa escrita.

### VIII. Segredos Fora do Código (NÃO-NEGOCIÁVEL)

**Regra**: Nenhuma credencial no código ou no histórico do repositório. Configuração sensível MUST
vir de variáveis de ambiente, com o `.env` fora do versionamento.

**Justificativa**: Credencial versionada é incidente de segurança permanente — o histórico do Git
não esquece, e a exposição sobrevive à remoção do arquivo.

**Obrigações**:
- `.env` listado no `.gitignore`; `.env.example` versionado documentando todas as chaves esperadas
  sem nenhum valor real.
- Credencial do Snowflake, chaves e tokens lidos exclusivamente de variável de ambiente.
- Credencial em log, em mensagem de erro ou em saída de console é PROIBIDA.

**Verificação**: varredura por padrões de credencial no repositório e no histórico retorna vazio.
`git check-ignore .env` confirma exclusão. Toda chave usada em código tem entrada correspondente
no `.env.example`.

### IX. Simplicidade Antes de Sofisticação

**Regra**: O fluxo completo funcionando tem precedência sobre qualquer otimização, abstração ou
recurso avançado.

**Justificativa**: Com 3 dias e uma apresentação ao vivo, um pipeline simples que roda do início
ao fim vale mais que um pipeline sofisticado que trava na demo. Otimizar antes de fechar o ciclo é
a forma mais comum de não entregar.

**Obrigações**:
- Nenhuma otimização de performance, camada de cache, generalização ou abstração antes de o
  pipeline rodar ponta a ponta com sucesso.
- Escolha sempre a solução mais simples que atende ao requisito; complexidade adicional exige
  justificativa escrita no PR ou ADR.
- Nenhuma ferramenta nova entra no projeto no último dia.
- Ao faltar tempo, corta-se escopo — nunca teste, documentação ou ensaio da demo.

**Verificação**: revisão recusa PR que introduza abstração, cache ou otimização sem justificativa
escrita, ou que chegue antes do pipeline completo estar verde. Diff de dependências no último dia
que introduza ferramenta nova reprova a revisão.

### X. Documentação é Entregável

**Regra**: O README MUST descrever arquitetura, pré-requisitos e o passo a passo completo para
rodar, e MUST estar correto no momento do merge.

**Justificativa**: O avaliador lê o README antes de rodar qualquer coisa. Documentação
desatualizada ou incompleta transforma um pipeline correto em uma entrega que ninguém consegue
reproduzir.

**Obrigações**:
- README com, no mínimo: visão da arquitetura medallion (RAW → STAGING → MARTS), pré-requisitos
  com versões, configuração de credenciais via `.env`, passo a passo de execução, e declaração de
  dados sintéticos.
- Todo comando citado no README MUST existir e funcionar exatamente como escrito.
- Mudança que altere execução, dependência ou arquitetura MUST atualizar o README no mesmo PR.

**Verificação**: os comandos do README são executados em máquina limpa e levam a MARTS populado e
testado. PR que altere execução, dependência ou arquitetura sem tocar o README é reprovado.

## Restrições Técnicas Adicionais

- **Prazo**: 3 dias corridos, com entrega final em apresentação ao vivo. O escopo se ajusta ao
  prazo; teste, documentação e ensaio da demo não são cortáveis (Princípio IX).
- **Warehouse**: Snowflake, conta trial, com os schemas `RAW`, `STAGING` e `MARTS`
  (Princípios I e III).
- **Stack**: Python para geração, ingestão e orquestração; SQL para transformação; orquestração e
  demais ferramentas open-source rodando localmente.
- **Custo**: nenhum recurso pago. Warehouse no menor tamanho, com auto-suspend (Princípio I).
- **Segredos**: `.env` fora do versionamento, `.env.example` versionado (Princípio VIII).
- **Dados**: 100% sintéticos com seed fixa; nenhum dado pessoal real em nenhuma camada
  (Princípio VI).
- **Observabilidade mínima**: cada execução registra data lógica do lote, linhas lidas, linhas
  escritas por camada, duração e resultado dos testes. Log estruturado; `print` solto é PROIBIDO
  em código de pipeline.

## Fluxo de Desenvolvimento e Portões de Qualidade

Todo PR MUST passar pelo checklist abaixo antes do merge; qualquer item reprovado bloqueia:

1. Nenhuma dependência de recurso pago; warehouse com tamanho mínimo e auto-suspend declarados em
   código (Princípio I).
2. O pipeline roda ponta a ponta com um único comando, sem passo manual (Princípio II).
3. RAW sem transformação, STAGING tipada e limpa, MARTS com métricas; nenhum salto de camada
   (Princípio III).
4. Teste de dupla execução do mesmo lote passa, sem duplicação (Princípio IV).
5. Todo modelo novo de STAGING e MARTS tem testes de chave, e MARTS tem teste de sanidade de
   negócio; falha aborta o pipeline (Princípio V).
6. Dados sintéticos com seed fixa; checksum estável entre execuções; nenhum dado pessoal real
   (Princípio VI).
7. Geração e ingestão em Python com type hints e docstrings; transformação em SQL (Princípio VII).
8. Nenhuma credencial no diff ou no histórico; `.env.example` atualizado (Princípio VIII).
9. Nenhuma otimização ou abstração antes do fluxo completo verde, e nenhuma sem justificativa
   escrita (Princípio IX).
10. README atualizado no mesmo PR quando execução, dependência ou arquitetura mudam
    (Princípio X).

Complexidade não justificada por escrito é motivo suficiente para recusa de PR.

## Governance

- Esta constituição PREVALECE sobre spec, plano, tarefas e implementação. Em conflito, a
  constituição vence e o artefato conflitante é corrigido.
- Emendas exigem ADR em `docs/adr/` registrando o problema, as alternativas consideradas e a
  decisão, além de incremento de versão semântica desta constituição.
- Versionamento: MAJOR para remoção ou redefinição incompatível de princípio; MINOR para novo
  princípio ou expansão material de guia; PATCH para clarificação, redação ou correção não
  semântica.
- Princípios marcados NÃO-NEGOCIÁVEL não admitem exceção pontual, apenas emenda formal com ADR e
  bump MAJOR.
- Conformidade é verificada a cada PR pelo checklist da seção anterior; a evidência objetiva de
  cada princípio é o teste ou artefato nomeado em seu critério de verificação.

**Version**: 2.0.0 | **Ratified**: 2026-09-08 | **Last Amended**: 2026-09-11
