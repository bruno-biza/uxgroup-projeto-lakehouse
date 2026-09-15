-- FR-014 vs FR-013: o volume de engajamento inclui TODAS as apostas validas,
-- inclusive pendentes e canceladas - criterio deliberadamente diferente do GGR.
--
-- Se este teste falhar porque alguem "corrigiu" o modelo para bater com o GGR,
-- a correcao e que esta errada: sao metricas de naturezas diferentes.
with esperado as (
    select
        data_aposta,
        coalesce(sum(valor_apostado), 0) as volume_esperado
    from {{ ref('fct_apostas') }}
    group by data_aposta
)

select
    a.data_aposta,
    a.volume_apostado as no_agregado,
    e.volume_esperado as recalculado
from {{ ref('agg_engajamento_diario') }} as a
inner join esperado as e on a.data_aposta = e.data_aposta
where a.volume_apostado <> e.volume_esperado
