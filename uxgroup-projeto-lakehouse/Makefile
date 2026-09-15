# Interface única do projeto. Todo comando do README é um alvo daqui, para que
# não exista passo que só o autor conhece (Princípio X, SC-008).

SHELL := /bin/bash
PYTHON ?= python
DATA ?= $(shell date -u +%F)
VOLUME ?= 50000
TAXA_NULOS ?= 0.03
TAXA_VALOR_INVALIDO ?= 0.02

# Fora do Docker, nada carrega o .env automaticamente (docker-compose usa
# env_file, mas Makefile/pytest/dbt não leem .env sozinhos). Toda CLI Python
# do projeto passa por common/config.py, que carrega o .env sozinha (via
# python-dotenv, tratando as aspas dos valores) — então os alvos abaixo não
# precisam de nenhum truque para isso. Só o `dbt`, que não é Python e lê
# credencial via env_var(), precisa da variável abaixo: `source` do bash
# interpreta `CHAVE="valor"` removendo as aspas corretamente, ao contrário de
# `include .env` do Make, que manteria as aspas literais no valor.
CARREGAR_ENV := set -a && . "$(CURDIR)/.env" && set +a &&

.DEFAULT_GOAL := ajuda
.PHONY: ajuda setup up down run run-local test test-integracao lint clean dashboard

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

run:  ## Dispara a DAG: make run DATA=2026-09-10 [TAXA_NULOS=] [TAXA_VALOR_INVALIDO=] [VOLUME=]
	docker compose exec -T airflow-scheduler \
		airflow dags trigger pipeline_bets \
		-e "$(DATA)T00:00:00+00:00" \
		--conf '{"volume": $(VOLUME), "taxa_nulos": $(TAXA_NULOS), "taxa_valor_invalido": $(TAXA_VALOR_INVALIDO)}'
	@echo "Execução disparada para $(DATA). Acompanhe em http://localhost:8080"

run-local:  ## Roda gerar + carregar + dbt fora do Airflow (depuração)
	$(PYTHON) -m generator.cli --data-lote $(DATA) --volume $(VOLUME) --saida ./dados
	$(PYTHON) -m ingestion.cli --data-lote $(DATA) --diretorio ./dados
	$(CARREGAR_ENV) cd dbt_bets && dbt build --fail-fast --vars '{"lote_data": "$(DATA)"}'

test:  ## Suíte padrão: pytest sem Snowflake + lint
	$(PYTHON) -m pytest
	$(PYTHON) -m ruff check generator ingestion common tests

test-integracao:  ## Testes que exigem credenciais reais do Snowflake
	$(PYTHON) -m pytest -m requires_snowflake

lint:  ## Ruff nos pacotes Python
	$(PYTHON) -m ruff check generator ingestion common tests

dashboard:  ## Painel opcional sobre MARTS (T087): pip install -e ".[dashboard]" antes da primeira vez
	$(PYTHON) -m streamlit run dashboard/app.py --server.headless true

clean:  ## Remove artefatos locais (não toca no Snowflake)
	rm -rf dados dbt_bets/target dbt_bets/logs .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
