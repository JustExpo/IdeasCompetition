# Единая точка команд (CLAUDE.md §11.3). Запуск приложения — только `make up`.
COMPOSE := docker compose
# Пароль тестовой БД в контейнере db — тот же, что в .env.example (dev only).
POSTGRES_PASSWORD ?= ideas-dev-password
TEST_DATABASE_URL ?= postgresql+asyncpg://ideas:$(POSTGRES_PASSWORD)@127.0.0.1:5433/ideas_test

.DEFAULT_GOAL := help
.PHONY: help up down restart logs migrate psql cli test-unit test-int e2e check contract test-contract

help: ## Список команд
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/'

up: ## Поднять app + db + mailpit (проверки, сборка, ожидание готовности)
	@./scripts/up.sh

down: ## Остановить контейнеры; данные (volume pgdata) сохраняются
	$(COMPOSE) down

restart: down up ## Перезапуск; простой 5–15 с

logs: ## Логи приложения
	$(COMPOSE) logs -f --tail=200 app

migrate: ## Применить миграции вручную (exec, не run)
	$(COMPOSE) exec app alembic upgrade head

psql: ## Консоль PostgreSQL
	$(COMPOSE) exec db psql -U ideas -d ideas

cli: ## Команды оператора: make cli ARGS="..." (модуль app.cli появится в IC-007)
	$(COMPOSE) exec app python -m app.cli $(ARGS)

test-unit: ## Unit-тесты backend и Vitest (frontend: сначала `cd frontend && npm ci`)
	cd backend && uv run pytest -m unit
	cd frontend && npm test

test-int: ## Integration-тесты на БД ideas_test в контейнере db (нужен `make up`)
	@$(COMPOSE) exec -T db psql -U ideas -d ideas -tAc "SELECT 1 FROM pg_database WHERE datname = 'ideas_test'" | grep -q 1 \
		|| $(COMPOSE) exec -T db createdb -U ideas ideas_test
	cd backend && TEST_DATABASE_URL='$(TEST_DATABASE_URL)' uv run pytest -m integration

e2e: ## E2E в браузере: app на время прогона переходит в режим e2e (БД ideas_e2e), затем возвращается
	@./scripts/e2e.sh

check: ## Формат, линтер, типы, границы модулей (backend и frontend)
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app tests && uv run lint-imports
	cd frontend && npm run format:check && npm run lint && npm run typecheck && npm run depcruise

contract: ## Обновить контракт: OpenAPI из приложения (без БД) → frontend/openapi.json → schema.gen.ts
	cd backend && uv run python -m app.cli export-openapi --output ../frontend/openapi.json
	cd frontend && npm run generate:types

test-contract: contract ## Контракт не разошёлся с кодом (нет diff), типы и тесты контракта проходят
	git diff --exit-code -- frontend/openapi.json frontend/src/api/schema.gen.ts
	cd frontend && npm run typecheck && npx vitest run src/api/contract.test.ts
