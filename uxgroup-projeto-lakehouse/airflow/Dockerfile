FROM apache/airflow:2.9.3-python3.11

# Por que dbt vive num virtualenv separado e não ao lado do Airflow:
#
# O Airflow 2.9 publica um arquivo de restrições que fixa versões de jinja2,
# click, packaging e urllib3. O dbt-core exige faixas diferentes de várias
# delas. Instalar os dois no mesmo interpretador resolve — quando resolve — num
# conjunto que quebra um dos lados em tempo de execução, tipicamente com erro de
# Jinja difícil de diagnosticar às vésperas da apresentação.
#
# Um virtualenv isolado dentro da mesma imagem elimina a colisão sem
# introduzir contêiner novo, e mantém o BashOperator simples: a DAG chama
# /opt/dbt-venv/bin/dbt por caminho absoluto.
USER root
RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/dbt-venv/bin/pip install --no-cache-dir \
        "dbt-core>=1.8,<2" \
        "dbt-snowflake>=1.8,<2" \
    && chown -R airflow: /opt/dbt-venv

USER airflow

# Dependências do código Python do projeto (gerador e ingestão). Estas sim
# convivem com o Airflow sem conflito.
RUN pip install --no-cache-dir \
    "faker>=25,<31" \
    "snowflake-connector-python>=3.12,<4"

ENV PYTHONPATH=/opt/projeto
ENV DBT_PROFILES_DIR=/opt/projeto/dbt_bets
