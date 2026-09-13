-- Dimensao de eventos esportivos.
-- Full-refresh: o volume nao justifica outra coisa, e a dimensao precisa conter
-- TODO o historico, nao apenas o lote corrente, senao fct_apostas perderia a
-- referencia de eventos de dias anteriores.
select
    evento_id,
    esporte,
    campeonato,
    time_casa,
    time_visitante,
    data_evento
from {{ ref('stg_eventos') }}
