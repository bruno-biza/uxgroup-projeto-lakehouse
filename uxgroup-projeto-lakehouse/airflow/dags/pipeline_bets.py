"""DAG diária do pipeline de apostas.

Seis tarefas em cadeia, exatamente como o plano define:

    gerar_lote → carregar_raw → dbt_run_staging → dbt_test_staging
               → dbt_run_marts → dbt_test_marts

Três decisões visíveis neste arquivo:

**A data lógica vem do ``{{ ds }}``**, nunca do relógio. É o parâmetro que faz
reexecutar um lote antigo produzir o mesmo resultado (FR-003, Princípio IV).

**dbt é chamado por caminho absoluto**, ``/opt/dbt-venv/bin/dbt``, porque vive
num virtualenv isolado dentro da imagem — ver ``airflow/Dockerfile`` para o
motivo.

**``dbt build`` em vez de ``dbt run`` seguido de ``dbt test``.** ``build``
intercala cada modelo com os seus testes, e com ``--fail-fast`` a execução para
no primeiro problema, antes de reconstruir os modelos a jusante. É o que
sustenta FR-020a: uma falha em STAGING não chega a tocar MARTS, e o analista
continua vendo os números do lote anterior. As tarefas ``dbt_test_*`` separadas
existem mesmo assim, porque a especificação exige um portão de teste explícito
e nomeado por camada (Princípio V) — e porque, na demo, ver a tarefa vermelha
com o nome ``dbt_test_staging`` comunica mais do que um ``build`` genérico.

``catchup=False`` de propósito: este é um projeto de demonstração e um catchup
acidental geraria dezenas de lotes, consumindo crédito do trial (Princípio I).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJETO = "/opt/projeto"
DBT = "/opt/dbt-venv/bin/dbt"
DIR_DBT = f"{PROJETO}/dbt_bets"
DIR_LOTES = os.environ.get("BETS_DATA_DIR_CONTAINER", "/opt/dados/lotes")

# Parâmetros do lote. Ficam como variáveis de módulo para que a demo possa
# alterá-los com `--conf` sem editar a DAG (ver docs/demo_script.md).
VOLUME_PADRAO = 50_000

argumentos_padrao = {
    "owner": "dados",
    "retries": 0,  # Falha de teste de dados não se resolve repetindo.
    "retry_delay": timedelta(minutes=1),
    "depends_on_past": False,
}

with DAG(
    dag_id="pipeline_bets",
    description="Gera, carrega, transforma e testa um lote diário de apostas.",
    start_date=datetime(2026, 9, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args=argumentos_padrao,
    tags=["bets", "medallion", "snowflake"],
    doc_md=__doc__,
    # Sobrepostos na execução manual, que é como o cenário 5 do quickstart
    # demonstra o portão de qualidade ao vivo:
    #   airflow dags trigger pipeline_bets --conf '{"taxa_nulos": 0.9}'
    params={
        "volume": VOLUME_PADRAO,
        "taxa_nulos": 0.03,
        "taxa_valor_invalido": 0.02,
    },
) as dag:
    volume = "{{ params.volume }}"
    taxa_nulos = "{{ params.taxa_nulos }}"
    taxa_valor = "{{ params.taxa_valor_invalido }}"

    gerar_lote = BashOperator(
        task_id="gerar_lote",
        bash_command=(
            f"cd {PROJETO} && python -m generator.cli "
            "--data-lote {{ ds }} "
            f"--volume {volume} "
            f"--saida {DIR_LOTES} "
            f"--taxa-nulos {taxa_nulos} "
            f"--taxa-valor-invalido {taxa_valor}"
        ),
        doc_md="Gera o lote sintético do dia com semente fixa (Princípio VI).",
    )

    carregar_raw = BashOperator(
        task_id="carregar_raw",
        bash_command=(
            f"cd {PROJETO} && python -m ingestion.cli "
            "--data-lote {{ ds }} "
            f"--diretorio {DIR_LOTES}"
        ),
        doc_md=(
            "Substitui as linhas da data lógica em RAW e recarrega "
            "(decisão D1). Idempotente por construção."
        ),
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"cd {DIR_DBT} && {DBT} run --fail-fast "
            "--select staging "
            "--vars '{\"lote_data\": \"{{ ds }}\"}'"
        ),
        doc_md="Limpa, tipa, deduplica e separa os inválidos na quarentena.",
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=(
            f"cd {DIR_DBT} && {DBT} test "
            "--select staging "
            "--vars '{\"lote_data\": \"{{ ds }}\"}'"
        ),
        doc_md=(
            "Portão do Princípio V: falha aqui aborta a DAG e dbt_run_marts "
            "não executa. MARTS permanece no estado do lote anterior."
        ),
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            f"cd {DIR_DBT} && {DBT} run --fail-fast "
            "--select marts "
            "--vars '{\"lote_data\": \"{{ ds }}\"}'"
        ),
        doc_md="Dimensões, fatos incrementais e os quatro agregados diários.",
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=(
            f"cd {DIR_DBT} && {DBT} test "
            "--select marts "
            "--vars '{\"lote_data\": \"{{ ds }}\"}'"
        ),
        doc_md=(
            "Testes de chave, de domínio e de sanidade de negócio das métricas."
        ),
    )

    (
        gerar_lote
        >> carregar_raw
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_marts
        >> dbt_test_marts
    )
