-- Warehouse do projeto.
--
-- Os três parâmetros abaixo são a evidência objetiva do Princípio I (Custo Zero):
-- XSMALL é o menor tamanho disponível, AUTO_SUSPEND de 60s impede consumo de
-- crédito com o warehouse ocioso, e INITIALLY_SUSPENDED evita gastar crédito no
-- próprio setup. Nenhum dos três pode ser removido sem emenda à constituição.
CREATE WAREHOUSE IF NOT EXISTS WH_BETS WITH
WAREHOUSE_SIZE = 'XSMALL'
AUTO_SUSPEND = 60
AUTO_RESUME = TRUE
INITIALLY_SUSPENDED = TRUE
COMMENT = 'Warehouse unico do projeto bets. XSMALL + AUTO_SUSPEND=60 por Principio I.';
