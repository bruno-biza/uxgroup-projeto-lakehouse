-- File format e stage interno para a carga dos lotes CSV.
--
-- O formato espelha exatamente o contrato de escrita do gerador
-- (specs/002-betting-analytics-platform/contracts/csv-batch.md). Divergencia
-- entre os dois quebra a carga de forma silenciosa, entao os dois lados citam o
-- mesmo contrato.
CREATE FILE FORMAT IF NOT EXISTS BETS.RAW.FF_CSV_BETS
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_DELIMITER = ','
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    EMPTY_FIELD_AS_NULL = TRUE
    TRIM_SPACE = FALSE
    ENCODING = 'UTF8'
    COMMENT = 'CSV dos lotes sinteticos. Campo vazio e o unico jeito de representar nulo.';

-- Stage interno: nenhum bucket externo, nenhum servico pago (Principio I).
CREATE STAGE IF NOT EXISTS BETS.RAW.STG_LOTES
    FILE_FORMAT = BETS.RAW.FF_CSV_BETS
    COMMENT = 'Stage interno dos lotes diarios, particionado por data logica.';
