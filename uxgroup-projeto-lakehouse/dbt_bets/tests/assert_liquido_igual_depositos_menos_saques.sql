-- FR-015: identidade do liquido, inclusive quando negativo.
select data_transacao, total_depositado, total_sacado, liquido
from {{ ref('agg_financeiro_diario') }}
where liquido <> total_depositado - total_sacado
