# Plataforma Analítica de Apostas Esportivas

Pipeline de dados ponta a ponta para uma casa de apostas esportivas fictícia: um gerador produz
lotes diários sintéticos com problemas de qualidade injetados de propósito, e o pipeline os limpa,
valida, rastreia o que descartou e publica métricas de negócio no Snowflake.

> **Todos os dados são sintéticos.** Nenhum dado pessoal real é coletado, armazenado ou inferido.
> Os números deste projeto são gerados por código a partir de uma semente fixa e não representam
> nenhuma empresa, pessoa ou operação real.

## O problema que ele resolve

A empresa precisa acompanhar diariamente receita, volume apostado e engajamento, mas os dados
operacionais chegam sujos: apostas duplicadas, campos obrigatórios nulos, valores negativos e
datas de aposta posteriores à data do evento. Publicar métricas sobre esse material produz número
errado com aparência de número certo.

Este pipeline separa o joio do trigo **e mantém o joio rastreável**: registro inválido não é
apagado, vai para uma quarentena onde se sabe qual lote o trouxe, qual regra ele violou e em que
linha do arquivo original ele estava.

## Arquitetura

```text
┌──────────────┐    CSV      ┌──────────────┐  PUT + COPY INTO  ┌─────────────────────────┐
│  generator/  │ ──────────► │  ingestion/  │ ────────────────► │      BETS.RAW           │
│  Python      │  lote/dia   │  Python      │                   │  tudo VARCHAR, sem      │
│  seed fixa   │             │  substitui   │                   │  transformação          │
└──────────────┘             │  por lote    │                   └───────────┬─────────────┘
                             └──────────────┘                               │
                                                                            ▼
        ┌───────────────────────────────────────────────────────┐   ┌───────────────────┐
        │                    BETS.MARTS                         │   │   BETS.STAGING    │
        │  dim_apostadores   dim_eventos                        │◄──│  stg_*   limpo    │
        │  fct_apostas (merge)   fct_transacoes (merge)         │   │  stg_*_rejeitadas │
        │  agg_ggr_diario_esporte      agg_engajamento_diario   │   │  qua_registros_   │
        │  agg_financeiro_diario       agg_qualidade_lote       │   │      rejeitados   │
        └───────────────────────────────────────────────────────┘   └───────────────────┘
                                     ▲                                        ▲
                                     └────────────  dbt  ──────────────────────┘

  Orquestração: Airflow local, uma DAG diária de seis tarefas
  gerar_lote → carregar_raw → dbt_run_staging → dbt_test_staging → dbt_run_marts → dbt_test_marts
```

**RAW** guarda o dado como chegou — todas as colunas de negócio são `VARCHAR`, sem exceção. Isso é
desenho, não descuido: sem conversão de tipo, não existe conversão que falhe, e uma aposta com
valor negativo chega intacta à quarentena em vez de derrubar a carga.

**STAGING** tipa, padroniza, deduplica e separa. Cada entidade produz dois modelos: o limpo e a
quarentena. A soma das linhas dos dois é igual ao que RAW recebeu — invariante verificado por
teste.

**MARTS** publica quatro agregados diários. Os fatos são incrementais com `merge`; os agregados
são reconstruídos por inteiro a cada execução, e é isso que faz o GGR de um dia passado ser
recalculado quando uma aposta pendente daquele dia é resolvida num lote posterior.

## Pré-requisitos

| Item | Versão | Observação |
|---|---|---|
| Docker + Docker Compose | Engine 24+ | Airflow e Postgres sobem aqui |
| Python | 3.11 | Para o gerador e a suíte de testes fora do contêiner |
| Conta trial do Snowflake | — | Gratuita, 30 dias. Nenhum upgrade é necessário |
| Memória livre | ~4 GB | Airflow com scheduler e webserver |

Nenhum recurso pago é usado. O warehouse é `XSMALL` com `AUTO_SUSPEND = 60`, declarado no SQL de
setup versionado — ele se suspende sozinho e não consome crédito ocioso.

## Configuração

```bash
cp .env.example .env
# preencha SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER e SNOWFLAKE_PASSWORD
```

`SNOWFLAKE_ACCOUNT` é o identificador no formato `<org>-<conta>`, visível na URL do Snowsight.

O `.env` nunca é versionado. Confirme antes de qualquer commit:

```bash
git check-ignore .env    # deve imprimir: .env
```

## Como rodar

```bash
make setup                  # cria warehouse, database, schemas, stage e tabelas RAW
make up                     # sobe Postgres e Airflow (build da imagem na primeira vez)
make run DATA=2026-09-10    # dispara a DAG para a data lógica
```

A interface do Airflow fica em <http://localhost:8080> (`admin` / `admin`).

`make setup` é idempotente — todos os objetos usam `IF NOT EXISTS`. `make run` também: reprocessar
a mesma data substitui o lote em vez de somá-lo.

Para depurar fora do Airflow, executando as três etapas direto na máquina:

```bash
make run-local DATA=2026-09-10 VOLUME=50000
```

Outros alvos: `make test` (suíte padrão e lint), `make test-integracao` (testes que exigem
credenciais reais), `make down`, `make clean`, `make ajuda`.

### Painel de métricas (opcional)

Um painel Streamlit, somente leitura, sobre as tabelas de `MARTS` — GGR por esporte, engajamento,
financeiro e qualidade do lote. Fora do escopo obrigatório: nenhum critério de sucesso depende
dele.

```bash
pip install -e ".[dashboard]"   # uma vez
make dashboard                  # abre em http://localhost:8501
```

## As quatro perguntas que o projeto responde

```sql
-- Quanto a casa ganhou ontem, e em quais esportes?
SELECT data_aposta, esporte, total_apostado, premios_pagos, ggr, exposicao_pendente
FROM BETS.MARTS.AGG_GGR_DIARIO_ESPORTE
WHERE data_aposta = '2026-09-10' ORDER BY ggr DESC;

-- Como está o engajamento?
SELECT * FROM BETS.MARTS.AGG_ENGAJAMENTO_DIARIO ORDER BY data_aposta DESC;

-- Entrou mais dinheiro do que saiu?
SELECT * FROM BETS.MARTS.AGG_FINANCEIRO_DIARIO ORDER BY data_transacao DESC;

-- Quanto do lote foi descartado, e por quê?
SELECT entidade, motivo, qtd_rejeitados, taxa_rejeicao
FROM BETS.MARTS.AGG_QUALIDADE_LOTE
WHERE lote_data = '2026-09-10' ORDER BY qtd_rejeitados DESC;
```

Para voltar de uma métrica até o registro que foi descartado:

```sql
SELECT entidade, chave_natural, motivos, arquivo_origem, linha_origem, registro_original
FROM BETS.STAGING.QUA_REGISTROS_REJEITADOS
WHERE lote_data = '2026-09-10'
  AND ARRAY_CONTAINS('valor_nao_positivo'::VARIANT, motivos)
LIMIT 5;
```

⚠️ **Não some `ggr` com `exposicao_pendente`.** Um é receita realizada; o outro é dinheiro em
risco ainda não resolvido. O dicionário completo, com o que cada métrica inclui e exclui, está em
[docs/metricas.md](docs/metricas.md).

## Estrutura

```text
generator/          Geração sintética com semente fixa e injeção de defeitos
ingestion/          Carga em RAW: substituição por lote, PUT e COPY INTO
common/             Log estruturado e leitura de configuração
snowflake_setup/    DDL versionado: warehouse, database, schemas, stage, RAW
dbt_bets/           Modelos de STAGING e MARTS, testes de dados
airflow/            Imagem estendida e a DAG diária
tests/              pytest: unidade (sem Snowflake) e integração (com)
docs/               Arquitetura, dicionário de métricas, ADRs, roteiro da demo
specs/              Especificação, plano, contratos e tarefas (Spec Kit)
```

## Garantias verificadas por teste

| Garantia | Onde é verificada |
|---|---|
| Mesma semente produz arquivos byte a byte idênticos | `tests/unit/test_determinismo.py` |
| Reprocessar um lote não altera nenhum número | `tests/integration/test_idempotencia_pipeline.py` |
| Nenhum registro inválido chega às métricas | `dbt_bets/tests/assert_nenhum_invalido_em_fatos.sql` |
| Recebidos = aceitos + rejeitados, por lote e entidade | `assert_recebidos_igual_aceitos_mais_rejeitados.sql` |
| Registro descartado é rastreável até a linha do CSV | `tests/integration/test_qualidade_rastreavel.py` |
| Taxa alta de rejeição não bloqueia o pipeline | `tests/integration/test_qualidade_rastreavel.py` |
| Pendente resolvida recalcula o GGR da data original | `tests/integration/test_pendente_resolvida.py` |
| Nenhuma data corrente implícita no código | `tests/unit/test_data_logica.py` |

## Documentação

- [Arquitetura e linhagem](docs/arquitetura.md)
- [Dicionário de métricas](docs/metricas.md) — o que cada número inclui e, principalmente, o que
  não inclui
- [Roteiro da demonstração](docs/demo_script.md)
- [Decisões de arquitetura (ADRs)](docs/adr/)
- [Especificação e plano](specs/002-betting-analytics-platform/) — incluindo as decisões técnicas
  com as alternativas que foram rejeitadas, em
  [research.md](specs/002-betting-analytics-platform/research.md)
