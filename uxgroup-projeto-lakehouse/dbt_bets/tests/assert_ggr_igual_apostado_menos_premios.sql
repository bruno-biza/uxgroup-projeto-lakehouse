-- FR-013: identidade do GGR.
-- Se esta relacao quebrar, o numero que abre a apresentacao esta errado.
select data_aposta, esporte, total_apostado, premios_pagos, ggr
from {{ ref('agg_ggr_diario_esporte') }}
where ggr <> total_apostado - premios_pagos
