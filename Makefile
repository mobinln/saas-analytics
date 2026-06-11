# saas-analytics — common developer tasks.
#
# Run `make` (or `make help`) for the target list. `.env` is loaded
# automatically when present, so `make run` picks up local config.

ifneq (,$(wildcard .env))
include .env
export
endif

# ClickHouse container started by local_dev/docker-compose.yaml. Override on the
# command line if you run ClickHouse elsewhere, e.g. `make migrate CLICKHOUSE_CONTAINER=ch`.
CLICKHOUSE_CONTAINER ?= my-clickhouse
CLICKHOUSE_USER      ?= eventaggregator
CLICKHOUSE_PASSWORD  ?=
MIGRATIONS_DIR       := migrations

.DEFAULT_GOAL := help
.PHONY: help run bench test migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

run: ## Run the ingest server (loads .env)
	go run ./cmd/server

bench: ## Run the wrk load benchmark against a running server
	./local_dev/benchmark.sh

test: ## Run all unit tests
	go test ./...

migrate: ## Apply SQL migrations in order to the ClickHouse container
	@for f in $(sort $(wildcard $(MIGRATIONS_DIR)/*.sql)); do \
		echo "applying $$f"; \
		docker exec -i $(CLICKHOUSE_CONTAINER) clickhouse-client \
			--user "$(CLICKHOUSE_USER)" --password "$(CLICKHOUSE_PASSWORD)" \
			--multiquery < "$$f" || exit 1; \
	done
	@echo "migrations applied"
