-- FR-014: ticket medio e NULO, nunca zero, quando nao ha aposta na data.
--
-- Zero afirmaria que o ticket medio foi zero; o correto e que nao existe
-- ticket medio. E tambem a prova de que nao ha divisao por zero escondida.
select
    data_aposta,
    qtd_apostas,
    ticket_medio
from {{ ref('agg_engajamento_diario') }}
where
    (qtd_apostas = 0 and ticket_medio is not null)
    or (qtd_apostas > 0 and ticket_medio is null)
