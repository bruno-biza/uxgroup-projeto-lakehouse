{% macro apagar_orfaos_do_lote(chave, fonte) %}
{#-
    Estende a substituicao por lote da decisao D1 (RAW, ver research.md) ate a
    camada de fato. `merge` so insere ou atualiza por chave - nunca remove.
    Sem este DELETE previo, regerar a mesma `lote_data` com conteudo diferente
    (outro volume ou taxa de defeito) deixa no fato as chaves da geracao
    anterior que nao sobrevivem na nova, orfas de dimensoes full-refresh que so
    conhecem a geracao atual.

    So apaga linha cuja `lote_data` AINDA e a deste lote: uma linha cujo
    `lote_data` ja migrou para um lote posterior (FR-019b, aposta pendente
    resolvida depois) fica fora do escopo e nao e tocada.
    -#}
    {% if is_incremental() and var('lote_data', '') != '' %}
    delete from {{ this }}
    where lote_data = '{{ var("lote_data") }}'
      and {{ chave }} not in (
          select {{ chave }}
          from {{ fonte }}
          where lote_data = '{{ var("lote_data") }}'
      )
{% endif %}
{% endmacro %}
