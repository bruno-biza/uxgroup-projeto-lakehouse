{#
    Usa o schema customizado LITERALMENTE, em vez de concatená-lo ao schema do
    perfil.

    Por que esta macro existe: o comportamento padrão do dbt é
    `<schema do perfil>_<schema customizado>`. Com `schema: STAGING` no
    profiles.yml e `+schema: STAGING` / `+schema: MARTS` no dbt_project.yml, os
    modelos iriam para `BETS.STAGING_STAGING` e `BETS.STAGING_MARTS` — e todo o
    SQL dos testes, do quickstart e da documentação referencia `BETS.STAGING` e
    `BETS.MARTS`.

    O Princípio III fixa exatamente três camadas com esses nomes, então o nome
    do schema é contrato, não convenção. Sobrescrever aqui é o jeito previsto
    pelo dbt de fazer valer um esquema de nomes próprio.

    Consequência a ter em mente: como o nome é literal, todos os alvos de um
    mesmo database escreveriam nos mesmos schemas. Num projeto com ambientes
    separados, é nesta macro que a distinção entra (por exemplo, prefixar com
    `target.name` quando não for produção). Hoje há um alvo só, `dev`, e a
    separação de ambientes está fora do escopo — ver plan.md.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
