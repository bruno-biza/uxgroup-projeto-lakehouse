-- SC-005: por lote e por entidade, recebidos = aceitos + rejeitados distintos.
--
-- A comparacao usa a contagem DISTINTA, nao a soma por motivo: um registro que
-- viola varias regras aparece em varias linhas de motivo e contaria varias
-- vezes. Este e o invariante que prova que nenhum registro se perdeu entre a
-- carga e a quarentena.
select
    lote_data,
    entidade,
    max(qtd_recebidos) as recebidos,
    max(qtd_aceitos) as aceitos,
    max(qtd_rejeitados_distintos) as rejeitados
from {{ ref('agg_qualidade_lote') }}
group by lote_data, entidade
having max(qtd_recebidos) <> max(qtd_aceitos) + max(qtd_rejeitados_distintos)
