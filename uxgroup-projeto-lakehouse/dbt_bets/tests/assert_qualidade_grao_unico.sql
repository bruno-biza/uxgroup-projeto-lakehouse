-- Grao de agg_qualidade_lote: (lote_data, entidade, motivo).
select
    lote_data,
    entidade,
    motivo,
    count(*) as linhas
from {{ ref('agg_qualidade_lote') }}
group by lote_data, entidade, motivo
having count(*) > 1
