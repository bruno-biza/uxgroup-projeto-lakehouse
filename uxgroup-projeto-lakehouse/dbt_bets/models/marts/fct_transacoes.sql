{{
    config(
        materialized='incremental',
        unique_key='transacao_id',
        incremental_strategy='merge'
    )
}}

-- Fato de transacoes financeiras. Mesma mecanica de fct_apostas: merge por
-- identificador, de modo que uma correcao vinda em lote posterior substitua a
-- linha em vez de acrescentar outra.
select
    transacao_id,
    apostador_id,
    data_transacao,
    tipo,
    valor,
    atualizado_em,
    lote_data
from {{ ref('stg_transacoes') }}

{% if is_incremental() and var('lote_data', '') != '' %}
    where lote_data = '{{ var("lote_data") }}'
{% endif %}
