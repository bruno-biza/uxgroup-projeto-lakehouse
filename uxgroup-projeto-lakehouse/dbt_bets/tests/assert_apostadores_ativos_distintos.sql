-- FR-014: apostador com varias apostas no dia conta uma vez.
with esperado as (
    select data_aposta, count(distinct apostador_id) as ativos
    from {{ ref('fct_apostas') }}
    group by data_aposta
)

select
    a.data_aposta,
    a.apostadores_ativos as no_agregado,
    e.ativos as recalculado
from {{ ref('agg_engajamento_diario') }} as a
inner join esperado as e on a.data_aposta = e.data_aposta
where a.apostadores_ativos <> e.ativos
