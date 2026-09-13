{{ config(materialized='table') }}

-- Quarentena de apostadores (FR-010).
--
-- Registro invalido NAO e apagado: ele fica aqui com o conteudo original
-- preservado em VARIANT, o lote, o momento do descarte e TODOS os motivos
-- aplicaveis. Um registro que viola varias regras aparece uma vez so, com
-- varios itens em `motivos` - e por isso que o invariante de SC-005 compara
-- contagem distinta, nao a soma por motivo.
--
-- Materializado como TABELA, nao view, e a decisao importa: numa view,
-- `current_timestamp()` seria avaliado a cada consulta e `rejeitado_em`
-- marcaria sempre "agora", o que e pior que nao ter a coluna. Como tabela, o
-- valor e gravado na construcao e significa o instante da execucao que
-- classificou o registro.
select
    'apostadores'            as entidade,
    apostador_id            as chave_natural,
    registro_original,
    motivos,
    arquivo_origem,
    linha_origem,
    lote_data,
    current_timestamp() as rejeitado_em
from {{ ref('int_apostadores_validados') }}
where array_size(motivos) > 0
