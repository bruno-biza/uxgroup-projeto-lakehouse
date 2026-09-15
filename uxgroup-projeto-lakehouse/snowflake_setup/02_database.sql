-- Database e as tres camadas do medallion (Principio III).
--
-- Cada schema tem responsabilidade unica e le apenas da camada anterior:
-- RAW (bruto, sem alteracao) -> STAGING (limpo e tipado) -> MARTS (metricas).
CREATE DATABASE IF NOT EXISTS BETS
COMMENT = 'Plataforma analitica de apostas esportivas sobre dados sinteticos.';

CREATE SCHEMA IF NOT EXISTS BETS.RAW
COMMENT = 'Dado como chegou. Todas as colunas de negocio sao VARCHAR: RAW nao tipa nem converte.';

CREATE SCHEMA IF NOT EXISTS BETS.STAGING
COMMENT = 'Dado limpo, tipado e deduplicado, mais os modelos de quarentena.';

CREATE SCHEMA IF NOT EXISTS BETS.MARTS
COMMENT = 'Dimensoes, fatos e agregados diarios de negocio.';
