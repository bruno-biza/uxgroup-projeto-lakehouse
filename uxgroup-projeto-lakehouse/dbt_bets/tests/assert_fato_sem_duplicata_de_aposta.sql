-- FR-019a: o merge substitui a versao da aposta, nunca acrescenta linha.
-- count(*) e count(distinct aposta_id) tem de ser iguais neste modelo.
select aposta_id, count(*) as linhas
from {{ ref('fct_apostas') }}
group by aposta_id
having count(*) > 1
