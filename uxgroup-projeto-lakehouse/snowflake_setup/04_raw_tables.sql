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
    APOSTADOR_ID VARCHAR,
    CRIADO_EM VARCHAR,
    ESTADO VARCHAR,
    ATUALIZADO_EM VARCHAR,
    ARQUIVO_ORIGEM VARCHAR,
    LINHA_ORIGEM NUMBER,
    CARREGADO_EM TIMESTAMP_NTZ,
    LOTE_DATA DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_EVENTOS (
    EVENTO_ID VARCHAR,
    ESPORTE VARCHAR,
    CAMPEONATO VARCHAR,
    TIME_CASA VARCHAR,
    TIME_VISITANTE VARCHAR,
    DATA_EVENTO VARCHAR,
    ATUALIZADO_EM VARCHAR,
    ARQUIVO_ORIGEM VARCHAR,
    LINHA_ORIGEM NUMBER,
    CARREGADO_EM TIMESTAMP_NTZ,
    LOTE_DATA DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_APOSTAS (
    APOSTA_ID VARCHAR,
    APOSTADOR_ID VARCHAR,
    EVENTO_ID VARCHAR,
    DATA_APOSTA VARCHAR,
    VALOR_APOSTADO VARCHAR,
    ODD VARCHAR,
    STATUS VARCHAR,
    PREMIO_PAGO VARCHAR,
    ATUALIZADO_EM VARCHAR,
    ARQUIVO_ORIGEM VARCHAR,
    LINHA_ORIGEM NUMBER,
    CARREGADO_EM TIMESTAMP_NTZ,
    LOTE_DATA DATE
);

CREATE TABLE IF NOT EXISTS BETS.RAW.RAW_TRANSACOES (
    TRANSACAO_ID VARCHAR,
    APOSTADOR_ID VARCHAR,
    DATA_TRANSACAO VARCHAR,
    TIPO VARCHAR,
    VALOR VARCHAR,
    ATUALIZADO_EM VARCHAR,
    ARQUIVO_ORIGEM VARCHAR,
    LINHA_ORIGEM NUMBER,
    CARREGADO_EM TIMESTAMP_NTZ,
    LOTE_DATA DATE
);
