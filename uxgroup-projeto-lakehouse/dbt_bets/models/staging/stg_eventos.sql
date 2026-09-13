-- Eventos limpos e tipados. Somente a versao canonica e valida.
select
    evento_id,
    esporte,
    campeonato,
    time_casa,
    time_visitante,
    data_evento,
    atualizado_em,
    lote_data
from {{ ref('int_eventos_validados') }}
where array_size(motivos) = 0
