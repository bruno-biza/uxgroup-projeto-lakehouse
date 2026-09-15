-- GGR diario por esporte (US1, FR-013 e FR-013a).
--
-- Full-refresh de proposito. E o que faz FR-019b funcionar sem uma linha de
-- codigo de backfill: como o agregado e sempre uma funcao pura do estado
-- canonico de fct_apostas, uma aposta que sai de `pendente` num lote posterior
-- recalcula automaticamente a data original dela. Num volume de dezenas de
-- milhares de linhas isso custa segundos.
--
-- CONTRATO: `ggr` e `exposicao_pendente` NUNCA devem ser somados. Um e receita
-- realizada, o outro e dinheiro em risco ainda nao resolvido. A separacao foi
-- decisao explicita registrada em spec.md secao Clarifications.
select
    data_aposta,
    esporte,

    -- Somente apostas resolvidas entram nas tres colunas de receita.
    -- `cancelada` esta fora porque o valor e devolvido: nao ha receita.
    -- `pendente` esta fora porque ainda nao se sabe.
    coalesce(sum(case when status in ('ganha', 'perdida') then valor_apostado end), 0)
        as total_apostado,
    coalesce(sum(case when status in ('ganha', 'perdida') then premio_pago end), 0)
        as premios_pagos,
    -- Pode ser negativo, e nao ha truncamento em zero: um dia em que os premios
    -- superam o arrecadado e um prejuizo real, nao um zero.
    coalesce(sum(case when status in ('ganha', 'perdida') then valor_apostado end), 0)
    - coalesce(sum(case when status in ('ganha', 'perdida') then premio_pago end), 0)
        as ggr,

    -- Leitura separada, nunca somada ao GGR.
    coalesce(sum(case when status = 'pendente' then valor_apostado end), 0)
        as exposicao_pendente,

    count(case when status in ('ganha', 'perdida') then 1 end) as qtd_apostas_resolvidas

from {{ ref('fct_apostas') }}
group by data_aposta, esporte
