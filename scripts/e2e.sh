#!/usr/bin/env bash
# `make e2e`: единственный `app` переводится в режим e2e (БД `ideas_e2e`, тестовые часы),
# Playwright проходит сценарии, затем `app` возвращается в режим dev (CLAUDE.md §10.1, Р14).
set -euo pipefail
cd "$(dirname "$0")/.."

DB_NAME=ideas_e2e
MAILPIT_URL=http://127.0.0.1:8025
COMPOSE_E2E=(docker compose -f compose.yaml -f compose.e2e.yaml)

fail() { echo "ОШИБКА: $*" >&2; exit 1; }

command -v docker >/dev/null || fail "Docker не найден."
command -v npm >/dev/null || fail "Node.js (npm) не найден: нужен для Playwright."

# Что бы ни случилось, оператор не остаётся с приложением в тестовом режиме.
restore_dev() {
  status=$?
  if [ "${status}" -ne 0 ]; then
    echo "e2e завершился с ошибкой; лог приложения:" >&2
    "${COMPOSE_E2E[@]}" logs --no-color --tail=100 app >&2 || true
  fi
  echo "Возвращаем приложение в режим dev…"
  ./scripts/up.sh || echo "Не удалось вернуть режим dev: выполните make up" >&2
  exit "${status}"
}

[ -f .env ] || cp .env.example .env

"${COMPOSE_E2E[@]}" up -d --wait db mailpit
trap restore_dev EXIT

# Остановка app снимает его соединения с БД и singleton-блокировку: БД e2e пересоздаётся с нуля.
"${COMPOSE_E2E[@]}" stop app
docker compose exec -T db psql -U ideas -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${DB_NAME}" -c "CREATE DATABASE ${DB_NAME}" >/dev/null

"${COMPOSE_E2E[@]}" build
"${COMPOSE_E2E[@]}" up -d --wait --remove-orphans app
[ "$(curl -s -o /dev/null -D - http://127.0.0.1:8000/api/health | tr -d '\r' | grep -ci '^x-app-mode: e2e')" = 1 ] \
  || fail "Приложение не в режиме e2e."

curl -fsS -X DELETE "${MAILPIT_URL}/api/v1/messages" >/dev/null

cd e2e
[ -d node_modules ] || npm ci
npx playwright test "$@"
