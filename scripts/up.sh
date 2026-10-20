#!/usr/bin/env bash
# `make up`: проверки перед запуском, сборка, запуск и проверка результата (CLAUDE.md §11.3, §12).
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=ideas-competition
APP_CONTAINER=ideas-competition-app
APP_PORT=8000
ROLE_LABEL="org.ideas-competition.role=app"

fail() { echo "ОШИБКА: $*" >&2; exit 1; }

command -v docker >/dev/null || fail "Docker не найден. Установите Docker Desktop (Compose ≥ 2.20)."
docker info >/dev/null 2>&1 || fail "Демон Docker не отвечает. Запустите Docker Desktop и повторите."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создан .env из .env.example (значения только для разработки)."
fi

# Чужие контейнеры приложения не удаляем: показываем, чем их остановить самому.
foreign=$(docker ps -a --filter "label=${ROLE_LABEL}" --format '{{.Names}}' | grep -vx "${APP_CONTAINER}" || true)
if [ -n "${foreign}" ]; then
  echo "Найдены другие контейнеры приложения (допустим один):" >&2
  echo "${foreign}" | sed 's/^/  - /' >&2
  echo "Остановите их: docker rm -f $(echo "${foreign}" | tr '\n' ' ')" >&2
  exit 1
fi

# Порт занят чужим процессом: свой контейнер порт уже держит и перезапускается на месте.
running=$(docker ps --filter "name=^${APP_CONTAINER}$" --format '{{.Names}}')
if [ -z "${running}" ] && (exec 3<>"/dev/tcp/127.0.0.1/${APP_PORT}") 2>/dev/null; then
  fail "Порт ${APP_PORT} на 127.0.0.1 занят другим процессом. Освободите его и повторите."
fi

# Сборка отдельно от `up`: при неизменном образе и конфигурации `up` оставляет контейнер как есть
# (повторный `make up` не должен менять ID контейнера и обрывать работающий сервер).
if ! docker compose build || ! docker compose up -d --wait --remove-orphans; then
  echo "Запуск не удался. Последние строки лога приложения:" >&2
  docker compose logs --tail=50 app >&2 || true
  exit 1
fi

count=$(docker ps --filter "label=${ROLE_LABEL}" --format '{{.ID}}' | wc -l | tr -d ' ')
[ "${count}" = "1" ] || fail "Запущено контейнеров приложения: ${count}, ожидался 1."

echo
echo "Готово: проект ${PROJECT}, режим dev."
echo "  Приложение:  http://127.0.0.1:${APP_PORT}/api/health"
echo "  Почта (Mailpit): http://127.0.0.1:8025"
