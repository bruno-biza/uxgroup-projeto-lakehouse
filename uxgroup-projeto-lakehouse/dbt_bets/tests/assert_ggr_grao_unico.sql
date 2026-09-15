-- O grao de agg_ggr_diario_esporte e (data_aposta, esporte). Duplicidade aqui
-- significa que o group by perdeu uma coluna, e toda leitura do GGR passa a
-- somar duas vezes a mesma coisa.
select
    data_aposta,
    esporte,
    count(*) as linhas
from {{ ref('agg_ggr_diario_esporte') }}
group by data_aposta, esporte
having count(*) > 1
