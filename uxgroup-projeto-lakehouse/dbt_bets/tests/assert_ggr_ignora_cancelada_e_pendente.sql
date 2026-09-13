-- FR-013: apostas canceladas e pendentes ficam fora das colunas de receita.
--
-- Compara o agregado com o calculo independente sobre o fato. Uma divergencia
-- aqui significa que um status indevido entrou no GGR - o erro mais caro que
-- este projeto pode cometer, porque produz numero errado com cara de certo.
with esperado as (
    select
        data_aposta,
        esporte,
        coalesce(sum(case when status in ('ganha', 'perdida') then valor_apostado end), 0)
            as total_apostado
    from {{ ref('fct_apostas') }}
    group by data_aposta, esporte
)

select
    a.data_aposta,
    a.esporte,
    a.total_apostado as no_agregado,
    e.total_apostado as recalculado
from {{ ref('agg_ggr_diario_esporte') }} as a
inner join esperado as e
    on a.data_aposta = e.data_aposta and a.esporte = e.esporte
where a.total_apostado <> e.total_apostado
