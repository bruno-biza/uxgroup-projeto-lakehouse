-- FR-013a: a exposicao pendente soma apenas apostas com status `pendente`.
with esperado as (
    select
        data_aposta,
        esporte,
        coalesce(sum(case when status = 'pendente' then valor_apostado end), 0)
            as exposicao_pendente
    from {{ ref('fct_apostas') }}
    group by data_aposta, esporte
)

select
    a.data_aposta,
    a.esporte,
    a.exposicao_pendente as no_agregado,
    e.exposicao_pendente as recalculado
from {{ ref('agg_ggr_diario_esporte') }} as a
inner join esperado as e
    on a.data_aposta = e.data_aposta and a.esporte = e.esporte
where a.exposicao_pendente <> e.exposicao_pendente
