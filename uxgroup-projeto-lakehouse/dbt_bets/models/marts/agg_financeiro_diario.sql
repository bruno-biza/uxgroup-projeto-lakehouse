-- Movimentacao financeira diaria (US4, FR-015).
--
-- Este mart NAO se reconcilia com o GGR. Dinheiro movimentado e receita de jogo
-- sao grandezas distintas, e tentar amarrar uma na outra produz numero sem
-- significado.
select
    data_transacao,
    coalesce(sum(case when tipo = 'deposito' then valor end), 0) as total_depositado,
    coalesce(sum(case when tipo = 'saque' then valor end), 0) as total_sacado,
    -- Pode ser negativo: dia em que saiu mais do que entrou.
    coalesce(sum(case when tipo = 'deposito' then valor end), 0)
    - coalesce(sum(case when tipo = 'saque' then valor end), 0) as liquido,
    count(case when tipo = 'deposito' then 1 end) as qtd_depositos,
    count(case when tipo = 'saque' then 1 end) as qtd_saques
from {{ ref('fct_transacoes') }}
group by data_transacao
