-- Apostadores limpos e tipados. Somente a versao canonica e valida de cada
-- identificador; o resto esta em stg_apostadores_rejeitadas.
select
    apostador_id,
    criado_em,
    estado,
    atualizado_em,
    lote_data
from {{ ref('int_apostadores_validados') }}
where array_size(motivos) = 0
