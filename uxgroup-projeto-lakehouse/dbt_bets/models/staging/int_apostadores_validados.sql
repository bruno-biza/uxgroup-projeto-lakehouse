{{ config(materialized='ephemeral') }}

-- Tipagem, validacao e ordenacao canonica dos apostadores.
--
-- Este modelo e efemero de proposito: ele existe para que a regra de validacao
-- seja escrita UMA vez e consumida tanto pelo modelo limpo quanto pelo de
-- quarentena. Duplicar a regra nos dois seria o caminho mais curto para os dois
-- divergirem e o invariante recebidos = aceitos + rejeitados parar de fechar.
-- Sendo efemero, nao cria objeto no warehouse: o SQL e embutido como CTE.

with tipado as (

    select
        nullif(trim(apostador_id), '')      as apostador_id,
        try_to_date(criado_em)              as criado_em,
        nullif(trim(estado), '')            as estado,
        try_to_timestamp_ntz(atualizado_em) as atualizado_em,
        arquivo_origem,
        linha_origem,
        lote_data,
        object_construct(
            'apostador_id', apostador_id,
            'criado_em', criado_em,
            'estado', estado,
            'atualizado_em', atualizado_em
        )                                   as registro_original
    from {{ source('raw', 'raw_apostadores') }}

),

avaliado as (

    select
        *,
        -- A ordenacao canonica e a mesma dentro e entre lotes (decisao D6):
        -- vence o marcador de atualizacao mais recente. O desempate final por
        -- arquivo e linha de origem garante ordem TOTAL - sem ele, dois
        -- registros identicos deixariam row_number() escolher arbitrariamente e
        -- SC-002 falharia de forma intermitente.
        row_number() over (
            partition by apostador_id
            order by
                atualizado_em desc nulls last,
                criado_em desc nulls last,
                estado desc nulls last,
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
                when apostador_id is null or criado_em is null or estado is null
                     or atualizado_em is null
                then 'nulo_obrigatorio'
            end
        )) as motivos
    from avaliado

)

select * from motivado
