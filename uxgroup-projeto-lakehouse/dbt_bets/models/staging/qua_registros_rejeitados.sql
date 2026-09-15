-- Uniao das quatro quarentenas. Fonte unica de agg_qualidade_lote e o ponto de
-- entrada para o engenheiro de dados rastrear um registro descartado ate a
-- linha exata do CSV (FR-010, SC-004).
--
-- View sobre tabelas: a materializacao ja aconteceu nos modelos de origem, e
-- duplicar o dado aqui nao acrescentaria nada.
{% set entidades = ['apostadores', 'eventos', 'apostas', 'transacoes'] %}

{% for entidade in entidades %}
    select
        entidade,
        chave_natural,
        registro_original,
        motivos,
        arquivo_origem,
        linha_origem,
        lote_data,
        rejeitado_em
    from {{ ref('stg_' ~ entidade ~ '_rejeitadas') }}
    {% if not loop.last %}union all{% endif %}
{% endfor %}
