{{
    config(
        materialized='incremental',
        unique_key='transacao_id',
        incremental_strategy='merge',
        pre_hook="{{ apagar_orfaos_do_lote('transacao_id', ref('stg_transacoes')) }}"
    )
}}

-- Fato de transacoes financeiras. Mesma mecanica de fct_apostas: merge por
-- identificador, de modo que uma correcao vinda em lote posterior substitua a
-- linha em vez de acrescentar outra. O `pre_hook` e a mesma extensao da
-- substituicao por lote (D1) explicada em fct_apostas.sql.
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
