{{
    config(
        materialized='incremental',
        unique_key='aposta_id',
        incremental_strategy='merge'
    )
}}

-- Fato de apostas: uma linha por aposta, sempre no ultimo status conhecido.
--
-- O `merge` por `aposta_id` e o que implementa FR-019a. Quando um lote
-- posterior traz a mesma aposta com status final, a linha e SUBSTITUIDA, nunca
-- somada - e por isso que `count(*)` e `count(distinct aposta_id)` sao iguais
-- neste modelo, o que o teste de integracao verifica.
--
-- `esporte` vem desnormalizado de stg_apostas (que ja o carrega do evento) para
-- que agg_ggr_diario_esporte nao precise de join. E decisao de simplicidade,
-- nao de performance: um join a menos e um lugar a menos onde errar o grao.

select
    aposta_id,
    apostador_id,
    evento_id,
    data_aposta,
    esporte,
    valor_apostado,
    odd,
    status,
    premio_pago,
    -- Resultado da casa naquela aposta. NULO, nao zero, quando a aposta ainda
    -- nao foi resolvida: zero significaria "a casa nao ganhou nem perdeu", que
    -- e afirmacao diferente de "ainda nao se sabe".
    case
        when status in ('ganha', 'perdida') then valor_apostado - premio_pago
    end as resultado_casa,
    atualizado_em,
    lote_data

from {{ ref('stg_apostas') }}

{% if is_incremental() and var('lote_data', '') != '' %}
    -- Em execucao incremental, processa apenas as linhas que chegaram no lote
    -- corrente. Uma aposta de uma data anterior atualizada neste lote tem
    -- lote_data do lote corrente e data_aposta antiga, entao ela entra aqui e o
    -- merge corrige a linha antiga - que e exatamente o cenario de FR-019b.
    where lote_data = '{{ var("lote_data") }}'
{% endif %}
