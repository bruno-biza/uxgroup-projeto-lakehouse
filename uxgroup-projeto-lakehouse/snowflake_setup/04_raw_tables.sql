-- Tabelas da camada RAW.
--
-- TODAS as colunas de negocio sao VARCHAR, sem excecao. Isto e desenho, nao
-- descuido (FR-004, Principio III): RAW preserva o registro como chegou, e sem
-- conversao de tipo nao existe conversao que falhe. E o que permite que uma
-- aposta com valor negativo ou data impossivel chegue intacta a quarentena em
-- vez de derrubar a carga.
--
-- Consequencia deliberada: um erro de COPY INTO aqui significa arquivo
-- corrompido (problema de infraestrutura), nunca dado sujo (problema esperado).
-- Por isso ON_ERROR = ABORT_STATEMENT e seguro na ingestao.
--
-- As quatro colunas de metadados sao identicas em todas as tabelas:
--   arquivo_origem / linha_origem -> rastro ate a linha do CSV (FR-010)
--   carregado_em                  -> auditoria da carga
--   lote_data                     -> chave de substituicao por lote (decisao D1)

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_APOSTADORES (
    apostador_id    VARCHAR,
    criado_em       VARCHAR,
    estado          VARCHAR,
    atualizado_em   VARCHAR,
    arquivo_origem  VARCHAR,
    linha_origem    NUMBER,
    carregado_em    TIMESTAMP_NTZ,
    lote_data       DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_EVENTOS (
    evento_id       VARCHAR,
    esporte         VARCHAR,
    campeonato      VARCHAR,
    time_casa       VARCHAR,
    time_visitante  VARCHAR,
    data_evento     VARCHAR,
    atualizado_em   VARCHAR,
    arquivo_origem  VARCHAR,
    linha_origem    NUMBER,
    carregado_em    TIMESTAMP_NTZ,
    lote_data       DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_APOSTAS (
    aposta_id       VARCHAR,
    apostador_id    VARCHAR,
    evento_id       VARCHAR,
    data_aposta     VARCHAR,
    valor_apostado  VARCHAR,
    odd             VARCHAR,
    status          VARCHAR,
    premio_pago     VARCHAR,
    atualizado_em   VARCHAR,
    arquivo_origem  VARCHAR,
    linha_origem    NUMBER,
    carregado_em    TIMESTAMP_NTZ,
    lote_data       DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_TRANSACOES (
    transacao_id    VARCHAR,
    apostador_id    VARCHAR,
    data_transacao  VARCHAR,
    tipo            VARCHAR,
    valor           VARCHAR,
    atualizado_em   VARCHAR,
    arquivo_origem  VARCHAR,
    linha_origem    NUMBER,
    carregado_em    TIMESTAMP_NTZ,
    lote_data       DATE
);
