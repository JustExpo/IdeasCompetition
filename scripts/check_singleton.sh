#!/usr/bin/env bash
# Проверка инварианта «не более одного контейнера приложения» (CLAUDE.md §12.4).
# Чужие контейнеры не удаляются. Шаги, которым не хватает инструментов, пропускаются явно.
set -uo pipefail
cd "$(dirname "$0")/.."

ROLE_LABEL="org.ideas-competition.role=app"
APP_CONTAINER=ideas-competition-app
failures=0

ok() { echo "  ✓ $*"; }
bad() { echo "  ✗ $*" >&2; failures=$((failures + 1)); }
count_apps() { docker ps -q --filter "label=${ROLE_LABEL}" | wc -l | tr -d ' '; }
app_id() { docker inspect -f '{{.Id}}' "${APP_CONTAINER}" 2>/dev/null; }

echo "1. make up → один контейнер приложения"
make up >/dev/null || { bad "make up не удался"; exit 1; }
first_id=$(app_id)
[ "$(count_apps)" = 1 ] && ok "контейнеров: 1" || bad "контейнеров: $(count_apps)"

echo "2. повторный make up → тот же контейнер"
make up >/dev/null
[ "$(app_id)" = "${first_id}" ] && ok "ID не изменился" || bad "контейнер пересоздан"

echo "3. два параллельных make up → один контейнер"
make up >/dev/null 2>&1 & make up >/dev/null 2>&1 &
wait
[ "$(count_apps)" = 1 ] && ok "контейнеров: 1" || bad "контейнеров: $(count_apps)"

echo "4. контейнер с тем же именем под другим проектом отклоняется демоном"
image=$(docker inspect -f '{{.Config.Image}}' "${APP_CONTAINER}")
if docker create --name "${APP_CONTAINER}" "${image}" >/dev/null 2>&1; then
  bad "демон создал второй контейнер с тем же именем"
else
  ok "конфликт имени, как и ожидалось"
fi

echo "5. docker compose run --rm app → сервер не стартует (advisory lock)"
output=$(timeout 120 docker compose run --rm --no-deps -T app 2>&1)
status=$?
if [ "${status}" -ne 0 ] && echo "${output}" | grep -q "Другой экземпляр приложения"; then
  ok "второй сервер отказался стартовать"
else
  bad "второй сервер не отказал (код ${status})"
  echo "${output}" | tail -5 >&2
fi
[ "$(docker ps -aq --filter "label=${ROLE_LABEL}" | wc -l | tr -d ' ')" = 1 ] \
  && ok "временный контейнер удалён" || bad "остался лишний контейнер приложения"

echo "6. локальный сервер на той же БД → отказ"
if command -v uv >/dev/null; then
  set -a; . ./.env; set +a
  password=${POSTGRES_PASSWORD:-ideas-dev-password}
  output=$(cd backend && DATABASE_URL="postgresql+asyncpg://ideas:${password}@127.0.0.1:5433/ideas" \
    SMTP_HOST=127.0.0.1 timeout 120 uv run python -m app.core.launcher 2>&1)
  status=$?
  if [ "${status}" -ne 0 ] && echo "${output}" | grep -q "Другой экземпляр приложения"; then
    ok "локальный сервер отказался стартовать"
  else
    bad "локальный сервер не отказал (код ${status})"
    echo "${output}" | tail -5 >&2
  fi
else
  echo "  – пропущено: нет uv"
fi

echo "7. итоговый подсчёт по label"
[ "$(count_apps)" = 1 ] && ok "контейнеров: 1" || bad "контейнеров: $(count_apps)"
[ "$(app_id)" = "${first_id}" ] && ok "исходный контейнер продолжает работать" || bad "исходный контейнер заменён"

echo "8. make down → 0 контейнеров, volume цел"
make down >/dev/null
[ "$(count_apps)" = 0 ] && ok "контейнеров: 0" || bad "контейнеров: $(count_apps)"
docker volume inspect ideas-competition_pgdata >/dev/null 2>&1 && ok "volume pgdata существует" || bad "volume pgdata потерян"

if [ "${failures}" -ne 0 ]; then
  echo "Проверок не пройдено: ${failures}" >&2
  exit 1
fi
echo "Инвариант выполняется."
