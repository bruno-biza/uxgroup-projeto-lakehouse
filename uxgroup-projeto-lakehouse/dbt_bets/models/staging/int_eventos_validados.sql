{{ config(materialized='ephemeral') }}

-- Tipagem, validacao e ordenacao canonica dos eventos esportivos.
-- Efemero pelo mesmo motivo de int_apostadores_validados: regra unica,
-- consumida pelo modelo limpo e pelo de quarentena.

with tipado as (

    select
        nullif(trim(evento_id), '') as evento_id,
        nullif(trim(esporte), '') as esporte,
        nullif(trim(campeonato), '') as campeonato,
        nullif(trim(time_casa), '') as time_casa,
        nullif(trim(time_visitante), '') as time_visitante,
        try_to_date(data_evento) as data_evento,
        try_to_timestamp_ntz(atualizado_em) as atualizado_em,
        arquivo_origem,
        linha_origem,
        lote_data,
        object_construct(
            'evento_id', evento_id,
            'esporte', esporte,
            'campeonato', campeonato,
            'time_casa', time_casa,
            'time_visitante', time_visitante,
            'data_evento', data_evento,
            'atualizado_em', atualizado_em
        ) as registro_original
    from {{ source('raw', 'raw_eventos') }}

),

avaliado as (

    select
        *,
        row_number() over (
            partition by evento_id
            order by
                atualizado_em desc nulls last,
                data_evento desc nulls last,
                esporte desc nulls last,
                arquivo_origem asc,
                linha_origem asc
        ) as versao
    from tipado

),

motivado as (

    select
        *,
        array_compact(array_construct(
            case when versao > 1 then 'duplicata' end,
            case
                when
                    evento_id is null or esporte is null or campeonato is null
                    or time_casa is null or time_visitante is null
                    or data_evento is null or atualizado_em is null
                    then 'nulo_obrigatorio'
            end,
            -- Fora do dominio fechado declarado em generator/config.py. O mesmo
            -- conjunto e testado com accepted_values: se os dois divergirem, o
            -- teste de dados reprova, que e o comportamento desejado.
            case
                when
                    esporte is not null
                    and esporte not in ('futebol', 'basquete', 'tenis', 'volei', 'mma')
                    then 'status_invalido'
            end
        )) as motivos
    from avaliado

)

select * from motivado
