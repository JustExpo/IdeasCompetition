# Самопроверка: стори 6 — реальное время, e2e, CI, сверка с ТЗ (IC-024–027, 030, 031)

Дата: 2026-10-23. Объём: `backend/app/{realtime,core/{access,config,middleware,testing}.py,main.py}`, события в `idea`/`vote`/`auth`,
`frontend/src/{api/{events,build,client}.ts,features/{realtime,environment,organizer},pages,shared/lib/lateAction.ts}`, `e2e/`, `compose.e2e.yaml`,
`scripts/{e2e.sh,check_singleton.sh,check_coverage.py}`, `.github/workflows/ci.yml`.

## Безопасность
- WebSocket: `Origin` проверяется до `accept` (CSWSH), сессия — по cookie и перепроверяется раз в 60 с, лимит 10 соединений на пользователя,
  входящие сообщения ≤ 1 КБ и только `ping`; тесты на каждый код закрытия (`test_realtime.py`).
- По сокету уходят только сигналы без данных; права и анонимность остаются в REST. В подаче события об идее получают автор и организатор,
  чужим пользователям не уходит ничего (`test_submission_events_reach_only_author_and_organizer`, `test_rejected_write_publishes_nothing`).
- Тестовые часы: маршрут существует только при `TEST_CLOCK_ENABLED`, а флаг допускается только при `APP_ENV=e2e` и имени БД `*_e2e`
  (проверка настроек); часы идут только вперёд; в `prod` маршрута нет. Заголовок `X-App-Mode: e2e` делает тестовый стенд узнаваемым.
- Лог: тест `test_log_hygiene.py` не нашёл пароль, токены, e-mail, тексты и идентификаторы идей. Найдено при написании: тестовый клиент httpx
  пишет полный URL (с id идеи) в корневой logger — это не лог приложения, в тесте его уровень поднят.
- Учётные данные в `e2e/support/env.ts` — заглушки из `.env.example` (dev only); gitleaks в CI.

## Структура
- События: аудиторию считают политики модулей (`plan_idea_events`, `plan_vote_events`), `realtime` не знает про фазы; публикация после commit.
- `core/testing.py` импортирует только `main` — контракт import-linter (всего 18, все выполнены).
- e2e вынесен в `e2e/` с собственным `package.json`; зависимости записаны в CLAUDE.md §17.

## Архитектура
- Решения Р1, Р2, Р4, Р8, Р12, Р14 не нарушены: один процесс и один контейнер приложения, e2e не поднимает второй стек.
- Отклонение Р8 из стори 4 (опрос раз в 5 с) закрыто: опроса нет, данные перечитываются по сигналу и при переподключении.

## Корректность
- Найдено и исправлено:
  1. Проверка default deny не видела маршруты из `include_router` (FastAPI 0.156) — забытая политика осталась бы незамеченной. Исправлено обходом `effective_candidates`, 6 регрессионных тестов.
  2. Тест остановки планировщика зависал: повторный `run_tick` перезапускал «застрявшую» задачу. Тест исправлен; поведение `stop()` не менялось.
  3. e2e показал: после 409 на дедлайне экран переходил в новую фазу, форма с ошибкой пропадала, и пользователь не видел причины. Добавлено сообщение страницы (`lateAction`), тест Vitest и сценарии e2e.
  4. Баннер потери связи совпал по тексту с баннером экрана организатора — второй переименован.
- Известные ограничения: `CSP connect-src 'self'` пропускает `ws://` того же хоста в Chromium (проверено в e2e); в Safari старых версий для `ws:` может понадобиться явный источник — не проверялось.
  Флаки `test_verify_fails_after_connection_is_killed` (стори 5) один раз упал в CI; если повторится — ловить `asyncpg.InternalClientError` в `SingletonLock.verify`.
- Не проверялось в окружении агента: `make up`, `make e2e`, `scripts/check_singleton.sh`, сборка образа (нет Docker) — проверяет CI.

## Команды и итог
- `ruff format --check`, `ruff check`, `mypy --strict app tests`, `lint-imports` — без замечаний; `pytest` — 633 passed (Python 3.12, PostgreSQL 16);
  покрытие веток `app/*/model` 98,6 %, `app/auth` 96,3 %.
- `prettier --check`, `eslint`, `tsc --noEmit`, `depcruise`, `vitest` (155), `vite build` — без замечаний; `make contract` — контракт не изменился.
- Playwright 1.56.1 (Chromium) против `APP_ENV=e2e` на PostgreSQL 16 и Mailpit: 8 из 8, повторный прогон на той же БД — 8 из 8.
