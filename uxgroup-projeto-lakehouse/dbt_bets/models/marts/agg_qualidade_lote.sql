-- Resumo de qualidade por lote (US2, FR-016 e FR-016a).
--
-- Grao: lote_data x entidade x motivo.
--
-- Duas decisoes que valem explicacao:
--
-- 1. `qtd_rejeitados_distintos` existe ao lado de `qtd_rejeitados` porque um
--    registro que viola varias regras aparece em VARIAS linhas de motivo, mas
--    conta UMA vez no total. Somar `qtd_rejeitados` por motivo daria um numero
--    maior que a realidade. O invariante de SC-005 usa a coluna distinta.
--
-- 2. Entidade sem nenhuma rejeicao aparece com motivo `sem_rejeicao` e
--    contagem zero, em vez de sumir da tabela. Um lote limpo tem de ser
--    visivel no resumo de qualidade: ausencia de linha e indistinguivel de
--    lote nao processado.
--
-- A taxa aqui e INFORMATIVA. Nenhum valor dela, nem 100%, interrompe a
-- execucao (FR-016a). O que bloqueia sao os testes estruturais.

{% set entidades = [
    ('apostadores', 'raw_apostadores', 'stg_apostadores'),
    ('eventos', 'raw_eventos', 'stg_eventos'),
    ('apostas', 'raw_apostas', 'stg_apostas'),
    ('transacoes', 'raw_transacoes', 'stg_transacoes')
] %}

with recebidos as (

    {% for entidade, fonte, _clean in entidades %}
        select
            lote_data,
            '{{ entidade }}' as entidade,
            count(*) as qtd_recebidos
        from {{ source('raw', fonte) }}
        group by lote_data
        {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

aceitos as (

    {% for entidade, _fonte, clean in entidades %}
        select
            lote_data,
            '{{ entidade }}' as entidade,
            count(*) as qtd_aceitos
        from {{ ref(clean) }}
        group by lote_data
        {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

rejeitados_distintos as (

    select
        lote_data,
        entidade,
        count(*) as qtd_rejeitados_distintos
    from {{ ref('qua_registros_rejeitados') }}
    group by lote_data, entidade

),

por_motivo as (

    -- Desaninha o array de motivos: uma linha por registro e por motivo.
    select
        q.lote_data,
        q.entidade,
        m.value::varchar as motivo,
        count(*) as qtd_rejeitados
    from {{ ref('qua_registros_rejeitados') }} as q,
        lateral flatten(input => q.motivos) as m
    group by q.lote_data, q.entidade, m.value::varchar

),

base as (

    select
        r.lote_data,
        r.entidade,
        coalesce(p.motivo, 'sem_rejeicao') as motivo,
        r.qtd_recebidos,
        coalesce(a.qtd_aceitos, 0) as qtd_aceitos,
        coalesce(p.qtd_rejeitados, 0) as qtd_rejeitados,
        coalesce(d.qtd_rejeitados_distintos, 0) as qtd_rejeitados_distintos
    from recebidos as r
    left join aceitos as a
        on r.lote_data = a.lote_data and r.entidade = a.entidade
    left join rejeitados_distintos as d
        on r.lote_data = d.lote_data and r.entidade = d.entidade
    left join por_motivo as p
        on r.lote_data = p.lote_data and r.entidade = p.entidade

)

select
    lote_data,
    entidade,
    motivo,
    qtd_recebidos,
    qtd_aceitos,
    qtd_rejeitados,
    qtd_rejeitados_distintos,
    case
        when qtd_recebidos = 0 then 0
        else round(qtd_rejeitados_distintos / qtd_recebidos, 4)
    end as taxa_rejeicao
from base
