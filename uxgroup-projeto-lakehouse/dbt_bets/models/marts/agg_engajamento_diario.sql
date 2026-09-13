-- Engajamento diario dos apostadores (US3, FR-014).
--
-- ATENCAO ao criterio, que difere do GGR DE PROPOSITO: esta e uma metrica de
-- ATIVIDADE, entao inclui TODAS as apostas validas, inclusive `pendente` e
-- `cancelada`. Por isso `volume_apostado` daqui nao e comparavel a
-- `total_apostado` de agg_ggr_diario_esporte, e comparar os dois sem essa
-- ressalva e o erro de leitura mais provavel destas tabelas.
select
    data_aposta,
    coalesce(sum(valor_apostado), 0) as volume_apostado,

    -- NULO, nao zero, quando nao ha aposta: zero afirmaria que o ticket medio
    -- foi zero, quando o correto e que nao existe ticket medio. `avg` ja
    -- devolve nulo sobre conjunto vazio, entao nao ha divisao por zero.
    avg(valor_apostado) as ticket_medio,

    -- Contagem distinta: um apostador com varias apostas no dia conta uma vez.
    count(distinct apostador_id) as apostadores_ativos,
    count(*) as qtd_apostas

from {{ ref('fct_apostas') }}
group by data_aposta
