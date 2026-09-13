-- FR-011 e SC-003: nenhum registro invalido influencia metrica alguma.
--
-- Este e o teste que sustenta a afirmacao central da US2. Ele varre o fato
-- procurando qualquer violacao das regras de qualidade; qualquer linha
-- devolvida e uma falha do portao de STAGING.
select
    aposta_id,
    'valor_nao_positivo' as violacao
from {{ ref('fct_apostas') }}
where valor_apostado <= 0

union all

select aposta_id, 'premio_negativo'
from {{ ref('fct_apostas') }}
where premio_pago < 0

union all

select aposta_id, 'chave_nula'
from {{ ref('fct_apostas') }}
where aposta_id is null or apostador_id is null or evento_id is null
   or data_aposta is null or status is null

union all

select aposta_id, 'status_fora_do_dominio'
from {{ ref('fct_apostas') }}
where status not in ('ganha', 'perdida', 'pendente', 'cancelada')

union all

-- Premio pago em aposta que nao foi ganha e inconsistencia estrutural.
-- Premio MAIOR que o valor apostado nao esta aqui de proposito: e o
-- comportamento normal de uma aposta ganha com odd alta.
select aposta_id, 'premio_em_status_indevido'
from {{ ref('fct_apostas') }}
where status in ('perdida', 'pendente', 'cancelada') and premio_pago <> 0

union all

select f.aposta_id, 'data_posterior_ao_evento'
from {{ ref('fct_apostas') }} as f
inner join {{ ref('dim_eventos') }} as e on f.evento_id = e.evento_id
where f.data_aposta > e.data_evento
