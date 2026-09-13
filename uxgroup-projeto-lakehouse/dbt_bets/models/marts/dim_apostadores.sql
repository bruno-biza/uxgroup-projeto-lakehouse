-- Dimensao de apostadores.
--
-- Nenhum dado pessoal real (Principio VI): nao ha nome, documento, e-mail nem
-- data de nascimento. `estado` e sigla de UF de dominio fechado.
--
-- `antiguidade_dias` usa a data do evento mais recente conhecido como
-- referencia, e nao current_date(): uma metrica que muda sozinha quando ninguem
-- executou nada quebraria SC-002.
with referencia as (
    select max(data_aposta) as data_referencia from {{ ref('stg_apostas') }}
)

select
    a.apostador_id,
    a.criado_em,
    a.estado,
    datediff('day', a.criado_em, r.data_referencia) as antiguidade_dias
from {{ ref('stg_apostadores') }} as a
cross join referencia as r
