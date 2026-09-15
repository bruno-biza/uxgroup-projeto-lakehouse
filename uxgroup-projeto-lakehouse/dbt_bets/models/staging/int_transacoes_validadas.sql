{{ config(materialized='ephemeral') }}

-- Tipagem, validacao e ordenacao canonica das transacoes financeiras.

with tipado as (

    select
        nullif(trim(transacao_id), '') as transacao_id,
        nullif(trim(apostador_id), '') as apostador_id,
        try_to_date(data_transacao) as data_transacao,
        nullif(trim(tipo), '') as tipo,
        try_to_number(valor, 12, 2) as valor,
        try_to_timestamp_ntz(atualizado_em) as atualizado_em,
        arquivo_origem,
        linha_origem,
        lote_data,
        object_construct(
            'transacao_id', transacao_id,
            'apostador_id', apostador_id,
            'data_transacao', data_transacao,
            'tipo', tipo,
            'valor', valor,
            'atualizado_em', atualizado_em
        ) as registro_original
    from {{ source('raw', 'raw_transacoes') }}

),

com_apostador as (

    select
        t.*,
        a.apostador_id is not null as apostador_existe
    from tipado as t
    left join {{ ref('stg_apostadores') }} as a
        on t.apostador_id = a.apostador_id

),

avaliado as (

    select
        *,
        row_number() over (
            partition by transacao_id
            order by
                atualizado_em desc nulls last,
                valor desc nulls last,
                tipo desc nulls last,
                arquivo_origem asc,
                linha_origem asc
        ) as versao
    from com_apostador

),

motivado as (

    select
        *,
        array_compact(array_construct(
            case when versao > 1 then 'duplicata' end,
            case
                when
                    transacao_id is null or apostador_id is null
                    or data_transacao is null or tipo is null or valor is null
                    or atualizado_em is null
                    then 'nulo_obrigatorio'
            end,
            case when valor <= 0 then 'valor_nao_positivo' end,
            case
                when apostador_id is not null and not apostador_existe
                    then 'apostador_inexistente'
            end,
            case
                when tipo is not null and tipo not in ('deposito', 'saque')
                    then 'status_invalido'
            end
        )) as motivos
    from avaliado

)

select * from motivado
