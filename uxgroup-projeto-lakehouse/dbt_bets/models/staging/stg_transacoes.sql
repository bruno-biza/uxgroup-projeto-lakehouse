-- Transacoes financeiras limpas e tipadas.
select
    transacao_id,
    apostador_id,
    data_transacao,
    tipo,
    valor,
    atualizado_em,
    lote_data
from {{ ref('int_transacoes_validadas') }}
where array_size(motivos) = 0
