{{ config(materialized='ephemeral') }}

-- Tipagem, validacao e ordenacao canonica das apostas. E o modelo central do
-- projeto: aqui se decide o que vira metrica e o que vira quarentena.
--
-- As integridades referenciais sao avaliadas contra os modelos LIMPOS de
-- apostador e evento, nao contra RAW. Uma aposta que referencia um apostador
-- que existe em RAW mas foi rejeitado tambem e invalida: aceita-la produziria
-- uma metrica apoiada num cadastro que o proprio pipeline recusou.

with tipado as (

    select
        nullif(trim(aposta_id), '') as aposta_id,
        nullif(trim(apostador_id), '') as apostador_id,
        nullif(trim(evento_id), '') as evento_id,
        try_to_date(data_aposta) as data_aposta,
        try_to_number(valor_apostado, 12, 2) as valor_apostado,
        try_to_number(odd, 8, 2) as odd,
        nullif(trim(status), '') as status,
        try_to_number(premio_pago, 12, 2) as premio_pago,
        try_to_timestamp_ntz(atualizado_em) as atualizado_em,
        arquivo_origem,
        linha_origem,
        lote_data,
        object_construct(
            'aposta_id', aposta_id,
            'apostador_id', apostador_id,
            'evento_id', evento_id,
            'data_aposta', data_aposta,
            'valor_apostado', valor_apostado,
            'odd', odd,
            'status', status,
            'premio_pago', premio_pago,
            'atualizado_em', atualizado_em
        ) as registro_original
    from {{ source('raw', 'raw_apostas') }}

),

com_evento as (

    select
        t.*,
        e.data_evento,
        e.esporte,
        e.evento_id is not null as evento_existe
    from tipado as t
    left join {{ ref('stg_eventos') }} as e
        on t.evento_id = e.evento_id

),

com_apostador as (

    select
        c.*,
        a.apostador_id is not null as apostador_existe
    from com_evento as c
    left join {{ ref('stg_apostadores') }} as a
        on c.apostador_id = a.apostador_id

),

avaliado as (

    select
        *,
        -- Mesma regra de FR-005 e FR-019a: vence o marcador de atualizacao mais
        -- recente, dentro e entre lotes. O desempate por arquivo e linha de
        -- origem fecha a ordem total.
        row_number() over (
            partition by aposta_id
            order by
                atualizado_em desc nulls last,
                valor_apostado desc nulls last,
                status desc nulls last,
                premio_pago desc nulls last,
                odd desc nulls last,
                data_aposta desc nulls last,
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
                    aposta_id is null or apostador_id is null or evento_id is null
                    or data_aposta is null or valor_apostado is null
                    or odd is null or status is null or premio_pago is null
                    or atualizado_em is null
                    then 'nulo_obrigatorio'
            end,
            case when valor_apostado <= 0 then 'valor_nao_positivo' end,
            case when data_aposta > data_evento then 'data_posterior_ao_evento' end,
            case
                when apostador_id is not null and not apostador_existe
                    then 'apostador_inexistente'
            end,
            case
                when evento_id is not null and not evento_existe
                    then 'evento_inexistente'
            end,
            -- Premio pago em aposta que nao foi ganha e inconsistencia
            -- estrutural. Premio MAIOR que o valor apostado, ao contrario, e
            -- comportamento normal de odd alta e nao e rejeitado.
            case
                when status in ('perdida', 'pendente', 'cancelada') and premio_pago <> 0
                    then 'premio_inconsistente'
            end,
            case
                when
                    status is not null
                    and status not in ('ganha', 'perdida', 'pendente', 'cancelada')
                    then 'status_invalido'
            end
        )) as motivos
    from avaliado

)

select * from motivado
