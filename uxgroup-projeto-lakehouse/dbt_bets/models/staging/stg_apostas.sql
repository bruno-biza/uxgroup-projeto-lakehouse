-- Apostas limpas e tipadas: a entidade central das metricas.
--
-- `array_size(motivos) = 0` e o portao unico de FR-011: registro invalido nao
-- fica a um WHERE esquecido de distancia da metrica, porque ele simplesmente
-- nao esta neste modelo.
select
    aposta_id,
    apostador_id,
    evento_id,
    data_aposta,
    valor_apostado,
    odd,
    status,
    premio_pago,
    esporte,
    data_evento,
    atualizado_em,
    lote_data
from {{ ref('int_apostas_validadas') }}
where array_size(motivos) = 0
