# Единая точка команд (CLAUDE.md §11.3). Запуск приложения — только `make up`.
COMPOSE := docker compose
# Пароль тестовой БД в контейнере db — тот же, что в .env.example (dev only).
POSTGRES_PASSWORD ?= ideas-dev-password
TEST_DATABASE_URL ?= postgresql+asyncpg://ideas:$(POSTGRES_PASSWORD)@127.0.0.1:5433/ideas_test

.DEFAULT_GOAL := help
.PHONY: help up down restart logs migrate psql cli test-unit test-int check

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

test-unit: ## Unit-тесты backend
	cd backend && uv run pytest -m unit

test-int: ## Integration-тесты на БД ideas_test в контейнере db (нужен `make up`)
	@$(COMPOSE) exec -T db psql -U ideas -d ideas -tAc "SELECT 1 FROM pg_database WHERE datname = 'ideas_test'" | grep -q 1 \
		|| $(COMPOSE) exec -T db createdb -U ideas ideas_test
	cd backend && TEST_DATABASE_URL='$(TEST_DATABASE_URL)' uv run pytest -m integration

check: ## Формат, линтер, типы, границы модулей
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app tests && uv run lint-imports
