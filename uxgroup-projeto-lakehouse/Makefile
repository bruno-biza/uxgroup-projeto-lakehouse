# Interface única do projeto. Todo comando do README é um alvo daqui, para que
# não exista passo que só o autor conhece (Princípio X, SC-008).

SHELL := /bin/bash
PYTHON ?= python
DATA ?= $(shell date -u +%F)
VOLUME ?= 50000

.DEFAULT_GOAL := ajuda
.PHONY: ajuda setup up down run run-local test test-integracao lint clean

ajuda:  ## Lista os alvos disponíveis
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup:  ## Cria warehouse, database, schemas, stage e tabelas RAW (idempotente)
	$(PYTHON) -m snowflake_setup.aplicar

up:  ## Sobe Postgres e Airflow (build da imagem na primeira vez)
	docker compose up -d --build
	@echo "Airflow em http://localhost:8080 (admin/admin)"

down:  ## Derruba os contêineres, preservando os volumes
	docker compose down

run:  ## Dispara a DAG para uma data: make run DATA=2026-09-10
	docker compose exec -T airflow-scheduler \
		airflow dags trigger pipeline_bets --logical-date "$(DATA)T00:00:00+00:00"
	@echo "Execução disparada para $(DATA). Acompanhe em http://localhost:8080"

run-local:  ## Roda gerar + carregar + dbt fora do Airflow (depuração)
	$(PYTHON) -m generator.cli --data-lote $(DATA) --volume $(VOLUME) --saida ./dados
	$(PYTHON) -m ingestion.cli --data-lote $(DATA) --diretorio ./dados
	cd dbt_bets && dbt build --fail-fast --vars '{"lote_data": "$(DATA)"}'

test:  ## Suíte padrão: pytest sem Snowflake + lint
	$(PYTHON) -m pytest
	$(PYTHON) -m ruff check generator ingestion common tests

test-integracao:  ## Testes que exigem credenciais reais do Snowflake
	$(PYTHON) -m pytest -m requires_snowflake

lint:  ## Ruff nos pacotes Python
	$(PYTHON) -m ruff check generator ingestion common tests

clean:  ## Remove artefatos locais (não toca no Snowflake)
	rm -rf dados dbt_bets/target dbt_bets/logs .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
