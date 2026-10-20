# Раунд 1. Техническая декомпозиция (Senior AI Engineer)

Источники: `tz.txt`, `context.md`, `CLAUDE.md` (целиком), `docs/edge-cases.md`, `docs/runbook.md`,
`docs/architecture-review.md` (Р2, Р14, разногласия, риски), `backend/` (модели, исключения, 26 тестовых
функций / 47 случаев, `pyproject.toml`). Код не писался, репозиторий не менялся.

Обозначения: **MVP** — нужно для минимального сквозного сценария «вход → конкурс → идея → голос → финал
(результаты видны)»; **Р** — расширение (обязательно по ТЗ, но после MVP); **О** — эксплуатация/качество.
Размер: **S** ≤ ~200 строк кода+тестов, полдня; **M** ~200–500 строк, день; **L** — дробить.
Каждая задача включает: тесты своего уровня, самопроверку §6.5 (`docs/code-review/…`), обновление
CLAUDE.md/README/edge-cases там, где меняется факт, строку в §17 при новом решении/зависимости.

---

## 1. Порядок и этапы

| Этап | Задачи | Итог этапа (проверяемо) | MR |
|---|---|---|---|
| E0. Инструменты | IC-001…IC-003 | `uv sync --frozen`, `ruff`, `mypy --strict`, `pytest -m unit`, `lint-imports` зелёные; конфигурация и часы покрыты unit | MR «Инструменты и ядро» |
| E1. Каркас приложения | IC-004…IC-012 | `make up` поднимает app+db+mailpit, `/api/health` = 200, миграции через entrypoint, advisory lock, CI backend | MR «Каркас» |
| E2. Пользователи и вход (MVP) | IC-013…IC-018 | Организатор из env входит, сотрудник регистрируется и входит; default deny; CSRF-Origin | MR «Вход» |
| E3. Конкурс → идея → голос → итог (MVP backend) | IC-019…IC-029 | Полный цикл по HTTP-тестам с FakeClock: создать конкурс, подать идею, проголосовать, после дедлайна финализация на тике, результаты видны всем | MR на каждый модуль (contest, idea, vote, result) |
| E4. Frontend MVP | IC-030…IC-037 | В браузере на `:8000` проходится сквозной сценарий; SPA внутри образа | MR «Frontend MVP» |
| E5. Полнота ТЗ (Р) | IC-038…IC-050 | Правка/удаление идей, письма (outbox + Mailpit), реальное время (WS), экран организатора live, напоминания | MR на каждую подсистему |
| E6. Доказуемость и эксплуатация | IC-051…IC-062 | e2e на два браузера, check_singleton, бэкап/restore-check, полный CI, CLI оператора, README и финальная сверка | MR «E2E и CI», «Эксплуатация», «Сдача» |

Принцип порядка: сначала то, без чего ничего нельзя проверить (инструменты → БД → health), затем
вертикальные срезы по модулям в порядке графа зависимостей §4.2 (`user → auth → contest → idea → vote → result`),
затем UI сквозного сценария, затем расширения. Каждая задача оставляет `make up` и `make test` зелёными.

---

## 2. Таблица задач

### E0. Инструменты и ядро

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-001 | Подключить зависимости рантайма backend и зафиксировать их в uv.lock | Зависимости §5 (fastapi, pydantic v2, pydantic-settings, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, structlog, argon2-cffi, email-validator, limits, aiosmtplib) и dev (pytest-asyncio, httpx, hypothesis, pytest-randomly, pytest-cov, import-linter, pip-audit); `.python-version`; маркеры pytest `unit/integration/commits`; ruff `TID251` banned-api (`datetime.now`, `time.time`, `time.sleep`, `asyncio.sleep` в tests); строки в §17 по каждой зависимости | `backend/pyproject.toml`, `uv.lock` | существующие 47 unit проходят через `uv run`; `pip-audit` | — | S | MVP |
| IC-002 | Добавить контракты import-linter для модулей и слоёв | `backend/.importlinter` по §4.2 (layers внутри 9 модулей, forbidden для model/exception, запрет чужих dao/controller/handler, common/core не импортируют модули, межмодульные layers); поправка графа §4.2 (см. §5, П-1, П-2) | `.importlinter`, CLAUDE.md §4.2 | `lint-imports` зелёный на текущем коде; намеренное нарушение в черновике падает (проверка вручную, в отчёт) | 001 | S | MVP |
| IC-003 | Добавить конфигурацию, часы и JSON-логирование приложения | `core/config.py` (Settings, `SecretStr`, правила §11.2, вывод всех ошибок без значений, код 2); `core/clock.py` (`Clock` Protocol, `SystemClock`); `tests/fakes.py` (`FrozenClock`); `core/logging.py` (structlog JSON, `request_id` в contextvars, маскирование e-mail) | `app/core/*` | unit: валидация env по средам (e2e-флаги только при `APP_ENV=e2e`, `WEB_CONCURRENCY≠1` → отказ, prod-пароль), маскирование, `caplog` без секретов | 001 | M | MVP |

### E1. Каркас приложения

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-004 | Создать приложение FastAPI с обработкой ошибок в формате problem+json | `app/main.py::create_app(settings)` (без БД при сборке), `core/http_errors.py` (`AppError` → problem+json, 422 FastAPI переупаковка, 500 `internal_error` без деталей), middleware: `X-Request-ID`, лимит тела 64 КБ (413), 415 не-JSON, 400 `malformed_json`, `Cache-Control: no-store`, заголовки безопасности; временный `/api/health` = 200 | `app/main.py`, `app/core/http_errors.py`, `app/core/middleware.py` | api (httpx ASGITransport): формат каждого кода ошибки, request_id в ответе, отсутствие стека | 003 | M | MVP |
| IC-005 | Подключить PostgreSQL и единую функцию транзакций | `core/db.py`: engine (пул и `server_settings` §7.3), общий `MetaData` с naming convention (имена constraint нужны для перевода `IntegrityError`), `run_in_transaction` (READ COMMITTED, повтор 40P01/40001 ≤3 с джиттером, `now` заново), ожидание БД при старте ≤60 с; health = `SELECT 1` ≤1 с; 503 `service_unavailable` + `Retry-After` при недоступной БД; `tests/integration/conftest.py` (отказ без суффикса `_test`, savepoint-изоляция, маркер `commits` + TRUNCATE) | `app/core/db.py`, tests | int: повтор транзакции на искусственном дедлоке (два соединения), health 503 при недоступной БД, conftest отказывается от не-`_test` БД | 004 | M | MVP |
| IC-006 | Настроить Alembic и проверку ревизии схемы при старте | `alembic.ini`, `migrations/env.py` (импорт всех `app.*.dao` в общий metadata, `transaction_per_migration`, `lock_timeout=5s`), пустая базовая ревизия; проверка «БД на ревизии X, приложению известна Y» → отказ старта; health учитывает совместимость схемы | `backend/migrations`, `app/core/db.py` | int: `upgrade head` → `alembic check` → `downgrade -1` → `upgrade head`; неизвестная ревизия → отказ | 005 | S | MVP |
| IC-007 | Добавить Dockerfile и compose.yaml с app, db и mailpit | Dockerfile (python 3.12 slim, uv, непривилегированный пользователь; стадия node — заглушка до IC-032), `compose.yaml` (`name`, `container_name: ideas-competition-app`, label `role=app`, порты на 127.0.0.1, лимиты, `init`, `stop_grace_period`, healthcheck через python, volume `pgdata`), `entrypoint.sh` (ожидание БД → миграции → `uvicorn --workers 1`), `.env.example` (dev only), `.dockerignore`, `.gitignore` (`.env`, `backups/`) | корень репозитория | ops: `docker compose up -d --wait` → health 200; `docker compose config` валиден | 006 | M | MVP |
| IC-008 | Добавить Makefile и скрипт запуска up.sh | `make up/down/restart/logs/migrate/psql/cli/test-unit/test-int/check`; `scripts/up.sh` (Docker запущен, порт свободен, preflight по label, `.env` из примера, `up -d --build --wait --remove-orphans`, postcheck, URL); создание БД `ideas_test` в `db` для `make test-int` | `Makefile`, `scripts/up.sh` | ops: повторный `make up` — тот же ID контейнера; `make down` сохраняет volume | 007 | M | MVP |
| IC-009 | Добавить singleton advisory lock процесса приложения | Выделенное соединение вне пула, `pg_try_advisory_lock`, повторы ≤30 с, сообщение с данными `pg_stat_activity`, проверка каждые 10 с, потеря → перезахват или health 503 + завершение; порядок в entrypoint: **lock → миграции → сервер** (миграции запускаются из процесса, держащего lock, — см. риск Т-3); `HOLD_SINGLETON_LOCK=false` для тестов/CLI | `app/core/singleton.py`, entrypoint | int: второй процесс против той же БД получает отказ; ops: `docker compose run --rm app` не стартует сервер | 008 | M | MVP |
| IC-010 | Добавить корректное завершение процесса по SIGTERM | lifespan: health → 503, `timeout_graceful_shutdown=10s`, остановка фоновых задач (заготовка реестра задач для планировщика/отправщика/WS), освобождение lock, `engine.dispose()` | `app/main.py`, `app/core/lifecycle.py` | int: lifespan shutdown освобождает lock и пул | 009 | S | MVP |
| IC-011 | Добавить CI для backend | GitHub Actions: `uv sync --frozen`, `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`, unit, integration (service `postgres:16`, БД `ideas_test`), цикл миграций; gitleaks | `.github/workflows/ci.yml` | сам CI зелёный на PR | 006 | S | MVP |
| IC-012 | Добавить политику доступа по умолчанию для маршрутов | Механизм объявления политики маршрута (зависимость/метка), allow-list публичных маршрутов §9.2, ошибка запуска при маршруте без политики; тест, перечисляющий `app.routes` | `app/core/access.py` (только механизм; политики — в модулях) | api: маршрут без политики → ошибка `create_app`; health публичен | 004 | S | MVP |

### E2. Пользователи и вход

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-013 | Добавить таблицы пользователей и сессий | `user/dao`, `auth/dao`: таблицы `users` (`UNIQUE(lower(email))`, CHECK role), `sessions` (token_hash bytea UNIQUE, FK CASCADE, индексы); миграция; перевод `IntegrityError` → `EmailTakenError` по имени constraint | `user/dao`, `auth/dao`, `migrations` | int: уникальность e-mail без учёта регистра, CHECK роли, каскад сессий | 006 | S | MVP |
| IC-014 | Добавить хэширование паролей Argon2id | `auth/service/password.py`: параметры OWASP, пул потоков + семафор 4, фиктивный хэш для неизвестного e-mail, NFKC, длина 10–128, `check_needs_rehash` | `auth/service` | unit: проверка/отказ, нормализация, граница длины 9/10/128/129; int: 10 одновременных проверок не превышают семафор | 003 | S | MVP |
| IC-015 | Создать организатора из окружения при старте и командой CLI | `user/service`: идемпотентное создание организатора из `ORGANIZER_*`; `app/cli.py` (каркас argparse) с `create-organizer`; вызов из lifespan | `user/service`, `app/cli.py` | int: повторный старт не дублирует; prod-пароль <16 → отказ (уже в IC-003) | 013, 014 | S | MVP |
| IC-016 | Добавить вход, выход и определение текущего пользователя | `auth/service`: создание сессии (`token_urlsafe(32)`, SHA-256, 7 дней), выход (`revoked_at`), `resolve_actor` (`sessions JOIN users`, `is_active`, без кэша); `auth/controller`: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`; cookie `sid` (HttpOnly, SameSite=Lax; prod `__Host-`/Secure); зависимости политик `authenticated`, `organizer_only`, `employee_only` | `auth/*` | api: 401 без/с истёкшей/отозванной сессией, деактивация действует со следующего запроса, смена роли, новый токен при каждом входе, одинаковый ответ для неизвестного e-mail и неверного пароля | 012, 015 | M | MVP |
| IC-017 | Добавить проверку Origin для изменяющих запросов | middleware: для POST/PUT/PATCH/DELETE `Origin` ∈ `ALLOWED_ORIGINS` (из `PUBLIC_BASE_URL`; `:5173` только dev), нет `Origin` → 403 | `app/core/middleware.py` | api: чужой/нет Origin → 403, GET не затронут | 016 | S | MVP |
| IC-018 | Добавить регистрацию сотрудников | `POST /api/auth/register`: email-validator, allow-list доменов (`email_domain_not_allowed`), 409 `email_taken`, роль employee; после регистрации — вход (допущение) | `user/service`, `user/controller` | api: регистр e-mail, IDN, чужой домен, дубль, лишние поля 422 | 016 | S | MVP |
| IC-019 | Ограничить частоту входа и регистрации | `limits` in-memory: вход 5/15 мин на (e-mail, IP), регистрация 5/ч на IP; 429 + `Retry-After`; per-IP выключается только в e2e | `auth/service`, `auth/controller` | api: 6-я попытка → 429; e2e-флаг вне e2e отклонён | 018 | S | Р (сразу после MVP) |

### E3. Конкурс → идея → голос → итог (backend)

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-020 | Добавить политики доступа к конкурсу, идеям, голосам и итогам | Чистые функции: `contest/model/policy.py` (`can_submit_ideas`, `can_view_results`, `allowed_actions(actor, phase)`), `idea/model/policy.py` (`can_view_idea`, `can_edit_idea`, `can_delete_idea`, `ensure_*`), `vote/model/policy.py` (`can_vote`, `ensure_can_vote`), `result/model/policy.py` (`can_view_authors`) | `*/model/policy.py` | unit: полная таблица истинности 3 фазы × роль × свой/чужой × активен; границы `d−1µs/d/d+1µs` | — (модели готовы) | M | MVP |
| IC-021 | Добавить создание конкурса организатором | `contest/dao` (таблица `contests`, CHECK порядка дедлайнов и длин, частичный индекс), миграция; `contest/service.create_contest` (нормализация текста, `deadline_in_past` по `Clock`); `POST /api/contests` (организатор); код ошибки порядка дедлайнов приведён к контракту (см. П-5) | `contest/*` | unit: проверки сервиса на FrozenClock; api: 403 сотруднику, 422 без смещения пояса, `deadlines_order`, `deadline_in_past` | 016, 020 | M | MVP |
| IC-022 | Добавить список и карточку конкурса с фазой и серверным временем | `GET /api/contests` (limit≤100, offset, `voting_deadline DESC, id DESC`, `{items,total}`), `GET /api/contests/{id}` (`phase`, `server_time`, `allowed_actions`, текст правила ничьей) | `contest/service`, `contest/controller` | api: 404, фаза на границах с FrozenClock, пагинация | 021 | S | MVP |
| IC-023 | Добавить таблицу идей и перевод ошибок её ограничений | `idea/dao`: `ideas` (uuid `gen_random_uuid()`, FK RESTRICT, CHECK длин, `UNIQUE(author_id, client_request_id)`, индекс), миграция; перевод `IntegrityError` | `idea/dao`, `migrations` | int: каждое ограничение | 021 | S | MVP |
| IC-024 | Добавить подачу идеи с идемпотентным повтором и лимитами | `idea/service.submit_idea` по §7.2 (поиск по ключу до фазы, `request_hash` с `contest_id`, `contest FOR SHARE`, `now` после блокировки, лимиты 20/1000, `ON CONFLICT DO NOTHING RETURNING`); `POST /api/contests/{id}/ideas` (201/200) | `idea/service`, `idea/controller` | api/int: 403 организатору, 409 `submission_closed` на `d` и `d+1µs`, повтор после дедлайна → 200, ключ с другим телом/конкурсом → 422, 21-я идея → 409, NUL/суррогат → 422 | 022, 023 | M | MVP |
| IC-025 | Добавить список идей конкурса с видимостью по фазам | `GET /api/contests/{id}/ideas`: подача — свои; голосование — все без автора и времени (`IdeaForVoting`, `ORDER BY id`, `is_mine`); финал — с авторами; три отдельные схемы с `extra="forbid"`; организатор до финала — без авторов | `idea/service`, `idea/controller` | contract: точные наборы ключей по фазам и ролям; int: чужие идеи в подаче не видны | 024 | M | MVP |
| IC-026 | Добавить голосование и отзыв голоса | `vote/dao` (`votes` PK, FK ideas CASCADE, users RESTRICT, idx voter_id), миграция; `vote/service.cast_vote/withdraw_vote` по §7.2 (видимость 404 → роль 403 → `own_idea_vote` → фаза 409); `PUT`/`DELETE /api/ideas/{id}/vote` (204); поле `my_vote` в списке идей | `vote/*`, `idea/service` (my_vote через vote.service — см. П-1) | int: 20 параллельных PUT → одна строка; повтор DELETE → 204; 409 на границе; организатор 403 | 025 | M | MVP |
| IC-027 | Добавить подсчёт голосов и выдачу результатов | `vote/dao.count_votes_by_idea`; `result/service.get_results` (одна функция для API, дашборда и писем, `rank_ideas`); `GET /api/contests/{id}/results` (`results_not_published` до финала для сотрудника; организатор — без авторов) | `result/*`, `vote/dao` | api: `d−1µs`/`d` для П8; ничья по `submitted_at`; пустой конкурс | 026 | M | MVP |
| IC-028 | Добавить планировщик фоновых тиков | `core/scheduler.py`: цикл тиков (интервал из настроек, первый тик при старте), `pg_try_advisory_xact_lock` на тик, широкий `except` только здесь с логом, реестр задач модулей, `run_tick(now)` для тестов, остановка между тиками; `RUN_SCHEDULER=false` в тестах | `app/core/scheduler.py`, lifespan | int: `run_tick` с FrozenClock; ошибка одной задачи не роняет цикл; параллельный тик пропускается | 010 | S | MVP |
| IC-029 | Добавить финализацию конкурса на тике | `result/service.finalize_due_contests` (`contest FOR UPDATE`, `now ≥ voting_deadline`, `UPDATE … WHERE finalized_at IS NULL RETURNING`, `winner_idea_id`); `result/handler` регистрирует задачу | `result/service`, `result/handler` | int: два тика → одна финализация; голос на границе ‖ финализация (два соединения, барьер) → голос в итоге или 409 | 027, 028 | M | MVP |

### E4. Frontend MVP

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-030 | Добавить экспорт OpenAPI и генерацию типов frontend | `app.cli export-openapi` (без БД), `make contract`, `frontend/openapi.json`, `openapi-typescript` → `schema.gen.ts`; `make test-contract` (+ `git diff --exit-code`) | `app/cli.py`, `Makefile`, `frontend/` | contract: diff пустой после генерации | 016 (можно раньше — по мере появления API) | S | MVP |
| IC-031 | Создать каркас frontend на React, Vite и TypeScript | Генератор `npm create vite` (запись в §15/README), `tsconfig` strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`, ESLint `strictTypeChecked`, Prettier, dependency-cruiser (`pages → features → api|shared`, fetch/WS только в `src/api`), Vitest + Testing Library + MSW, react-router, react-query, openapi-fetch-клиент, `shared/lib/serverTime.ts`; Vite proxy `/api` → `:8000` (+ws) | `frontend/*`, `.nvmrc` | Vitest: `serverTime` (смещение, сбитые часы) | 030 | M | MVP |
| IC-032 | Встроить сборку SPA в образ и отдачу статики приложением | Стадия node в Dockerfile (`npm ci && vite build`), FastAPI: статика + fallback на `index.html` для путей вне `/api`, CSP §9.3, кэширование ассетов; allow-list default deny учитывает SPA | `Dockerfile`, `app/main.py` | api: `/`, `/contests/1` → index.html, `/api/unknown` → 404 problem+json; заголовки CSP | 031, 012 | S | MVP |
| IC-033 | Добавить экраны входа и регистрации | Формы, обработка `code` (`invalid_credentials`, `email_taken`, `email_domain_not_allowed`, 429), выход, защита маршрутов по `/api/auth/me` | `features/auth`, `pages` | Vitest+MSW: ветки ошибок по `code` | 031, 018 | M | MVP |
| IC-034 | Добавить список конкурсов и создание конкурса организатором | Список с фазами, форма создания (локальное время → ISO со смещением, `DISPLAY_TZ` — см. О-6) | `features/contests` | Vitest: ошибки `deadlines_order`/`deadline_in_past` | 033, 022 | M | MVP |
| IC-035 | Добавить страницу конкурса с подачей идеи | Карточка конкурса, правило ничьей видно с фазы подачи, таймер до дедлайна по серверному времени, подача с `client_request_id` (генерирует SPA) и безопасным повтором, «мои идеи»; при наступлении дедлайна — перечитывание | `features/ideas`, `pages/contest` | Vitest: таймер на границе, 409 `submission_closed` показывает понятный текст | 034, 025 | M | MVP |
| IC-036 | Добавить голосование на странице конкурса | Список идей без авторов, кнопка голоса/отзыва (`my_vote`), запрет для своих (`is_mine`), обработка 409/403 | `features/voting` | Vitest: состояния кнопки, exhaustive switch по `phase` | 035, 026 | M | MVP |
| IC-037 | Добавить экран результатов конкурса | Таблица мест, авторы после финала, победитель, «идей нет» | `features/results` | Vitest: финал/до финала (организатор без авторов) | 036, 029 | S | MVP |

**Точка MVP:** после IC-037 сквозной сценарий проходит вручную в браузере; проверка — integration-тест
полного цикла (IC-029) + ручной прогон, зафиксированный в README «Состояние проекта».

### E5. Полнота ТЗ

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-038 | Добавить правку идеи с контролем версии | `PATCH /api/ideas/{id}` по §7.2 (блокировки → совпадение полей → фаза → `version` → UPDATE; `submitted_at` неизменен); UI правки с обработкой `stale_version` | `idea/*`, `features/ideas` | int: повтор своей правки после дедлайна → 200, `stale_version`, чужая → 404, после дедлайна → 409 | 024, 035 | M | Р |
| IC-039 | Добавить удаление идеи вместе с голосами | `DELETE /api/ideas/{id}` (404 чужой, 409 `idea_locked` в финале, каскад голосов); UI | `idea/*` | int: удаление ‖ голос (два соединения) → нет сиротских голосов, голос 404 | 026 | S | Р |
| IC-040 | Добавить эндпоинт экрана организатора | `GET /api/organizer/contests/{id}/dashboard` (`ideas_count`, `voters_count` — различные голосующие с текущими голосами, `results[]` без авторов до финала) в модуле `result` | `result/controller` | api: 403 сотруднику, числа после отзыва голоса/удаления идеи | 027 | S | Р |
| IC-041 | Добавить экран организатора во frontend | Счётчики и текущие результаты (сначала по запросу, live — в IC-045) | `features/organizer` | Vitest | 040, 037 | S | Р |
| IC-042 | Добавить outbox писем и шаблоны | `notification/dao` (`outbox_emails`, `UNIQUE(dedup_key)`, CHECK статусов, частичный индекс), миграция; `notification/service.enqueue_email` (в транзакции вызывающего, `ON CONFLICT DO NOTHING`); `templates.py` (plain text, `DISPLAY_TZ`) | `notification/*` | int: дубль `dedup_key` не создаётся; unit: шаблоны без управляющих символов в заголовках | 006 | M | Р |
| IC-043 | Ставить письма победителю и участникам при финализации | В `finalize_due_contests`: участники = авторы текущих идей + проголосовавшие; победителю — отдельный вид; «идей нет» — писем нет | `result/service` | int: состав получателей, повторный тик не дублирует, итог в письме = API | 029, 042 | S | Р |
| IC-044 | Добавить отправку писем из outbox через SMTP | `EmailSender` Protocol, адаптер aiosmtplib (таймаут 10 с, детерминированный `Message-ID`), `notification/handler` (тик + пробуждение `asyncio.Event` после commit), `FOR UPDATE SKIP LOCKED` пачкой 20, аренда 60 с, backoff `min(2^n мин, 1 ч)`, 8 попыток → `failed`, `not_after` → `expired`; `FakeMailSender` | `notification/*`, `tests/fakes.py` | int: все режимы FakeMailSender (успех, 4xx, 5xx, таймаут, обрыв, «отправлено, но commit упал») | 042, 028 | M | Р |
| IC-045 | Добавить шину событий с публикацией после commit | `realtime/service` (внутрипроцессная шина, `EventPublisher` Protocol), `realtime/model/policy.py` (адресаты по аудитории, см. П-2); публикация в сервисах idea/vote/result/auth после commit | `realtime/*`, сервисы | int: событие только после commit, при откате — нет; адресаты в фазе подачи | 026, 039 | M | Р |
| IC-046 | Добавить WebSocket-канал событий конкурса | `WS /api/contests/{id}/events`: Origin до `accept`, cookie-сессия (4401/4403), ≤10 соединений на пользователя, входящие ≤1 КБ (ping), перепроверка сессии раз в 60 с, `session_revoked` при выходе, закрытие 1012 при остановке, приветствие с `X-App-Build` | `realtime/controller`, `realtime/service` | int: CSWSH, 4401, лимит соединений, только сигналы без данных | 045, 017 | M | Р |
| IC-047 | Подключить события реального времени во frontend | `api/events.ts` (переподключение с backoff, refetch при переподключении, invalidate react-query по типу, exhaustive switch), live экран организатора, исчезновение удалённой идеи | `frontend/src/api`, features | Vitest+MSW: каждая ветка события | 046, 041 | M | Р |
| IC-048 | Добавить выбор получателей и таблицу напоминаний | `reminder/model.select_reminder_recipients` (по текущему участию), `reminder/dao` (`reminders` PK, CHECK, FK CASCADE), миграция | `reminder/*` | unit: отозвал все голоса / удалил единственную идею → получатель; организатор/неактивный — нет | 042 | S | Р |
| IC-049 | Ставить напоминания за сутки до закрытия раунда на тике | `reminder/service.enqueue_due_reminders` (`INSERT … SELECT … NOT EXISTS … ON CONFLICT DO NOTHING RETURNING` + outbox с `not_after=deadline` в одной транзакции), `reminder/handler` | `reminder/*` | int: два тика параллельно → одно напоминание; окно `d−24h−1µs/d−24h/d−1µs/d`; конкурс создан позже окна | 048, 044 | M | Р |
| IC-050 | Добавить заголовок версии сборки и предложение обновить страницу | `X-App-Build` в ответах и WS-приветствии; SPA сравнивает с собой | `app/main.py`, frontend | api, Vitest | 046 | S | Р |

### E6. Доказуемость и эксплуатация

| ID | Название коммита | Что входит | Компоненты | Тесты | Зав. | Разм. | MVP |
|---|---|---|---|---|---|---|---|
| IC-051 | Добавить режим e2e с тестовыми часами | `compose.e2e.yaml` (тот же `container_name`), `APP_ENV=e2e`, БД `ideas_e2e` (пересоздание перед прогоном), `core/testing` (часы только вперёд), `POST /api/__test__/clock` (политика `e2e_only`, после сдвига — синхронный тик, см. О-3), плашка «E2E MODE»; `make e2e` с `trap 'make up'` | `compose.e2e.yaml`, `app/core/testing`, `Makefile` | unit: маршрута нет вне e2e; ops: после `make e2e` app в dev | 028, 032 | M | О |
| IC-052 | Добавить e2e полного цикла конкурса с письмами | Playwright: организатор создаёт конкурс → сотрудники подают → сдвиг часов → голосование (без авторов, своя недоступна) → финал с авторами → письма в Mailpit API; правило ничьей видно | `e2e/` | e2e | 051, 037, 044 | M | О |
| IC-053 | Добавить e2e двух вкладок: голос, удаление идеи, экран организатора | П5 (две вкладки одного пользователя → один голос), П11 (удаление в A → исчезает в B ≤2 с), П7 (голос → цифра у организатора без перезагрузки) | `e2e/` | e2e | 051, 047 | M | О |
| IC-054 | Добавить e2e отправки после дедлайна при открытой странице | П2: форма идеи и кнопка голоса открыты → сдвиг часов → 409 и понятный текст; выход в одной вкладке → вторая 401 | `e2e/` | e2e | 051, 038 | S | О |
| IC-055 | Добавить скрипт проверки инварианта одного контейнера | `scripts/check_singleton.sh` по §12.4 (8 шагов, подсчёт по label, чужие контейнеры не удаляются) | `scripts/` | ops (локально и в CI) | 009 | S | О |
| IC-056 | Добавить бэкап и проверку восстановления БД | `scripts/backup.sh`, `restore_check.sh`, `make backup/restore-check/restore/destroy` (подтверждение именем проекта), права 600, 7 последних | `scripts/`, `Makefile` | ops: restore-check сверяет ревизию и число строк | 008 | M | О |
| IC-057 | Добавить команды оператора в CLI | `reset-password <email>` (отзывает сессии), `revoke-sessions --all`, `status` (outbox pending/failed/возраст, лаг планировщика, пул, ближайший дедлайн); `make status`; предупреждение в `up.sh` при дедлайне < 1 ч | `app/cli.py`, `user/auth/notification service` | int: CLI-функции против `ideas_test` | 044, 016 | M | О |
| IC-058 | Добавить очистку устаревших сессий и тел писем | Ежедневная задача тика: удаление истёкших сессий, `body → NULL` через 30 дней | `auth/service`, `notification/service`, handlers | int с FrozenClock | 044 | S | О |
| IC-059 | Добавить демо-данные для разработки | `SEED_DEMO` (только dev/e2e): сотрудники, конкурсы в разных фазах | `app/cli.py` или lifespan | int: идемпотентность; prod — запрещено (IC-003) | 039 | S | О |
| IC-060 | Расширить CI проверками frontend, контракта, зависимостей и образа | prettier/eslint/tsc/depcruise/vitest/vite build; `make test-contract`; `pip-audit`, `npm audit --audit-level=high`; сборка образа, `make up`, `check_singleton.sh`, smoke, backup+restore-check, `make e2e`, артефакт логов при падении; покрытие веток `*/model` ≥95 % | `.github/workflows` | CI зелёный | 052…056 | M | О |
| IC-061 | Добавить тест логов без персональных данных и паролей | Сквозной `caplog`-тест по основным сценариям (вход, подача, голос, письмо): нет паролей, токенов, cookie, текстов идей, связки автор↔идея | `tests/integration` | int | 044, 046 | S | О |
| IC-062 | Обновить README и сверить реализацию с ТЗ | Статусы §1, «Состояние проекта», «Следующим заходом», хронология §18, экспорт сессии (по согласию), приведение CLAUDE.md/edge-cases/runbook к фактическому (пометки «(проверено)») | документация | ручная сверка П1–П11 ↔ тесты | все | S | О |

Итого 62 задачи: MVP — 37 (IC-001…IC-037, кроме IC-019), Р — 13, О — 12. L-задач нет: всё, что
тянуло на L (каркас, вход, идеи, письма, WS, e2e), разбито.

---

## 3. Граф зависимостей и параллельность

```
001 ─┬─ 002
     └─ 003 ─ 004 ─┬─ 005 ─ 006 ─┬─ 007 ─ 008 ─┬─ 009 ─ 010 ─ 028 ─┐
                   │              │             ├─ 055, 056         │
                   │              ├─ 011        │                   │
                   │              ├─ 013 ─┐     │                   │
                   ├─ 012 ────────┼───────┼─ 016 ─┬─ 017            │
                   │              │  014 ─┴─ 015 ─┘  └─ 018 ─ 019   │
                   │              └─ 042 ─ 048                      │
 020 (без зависимостей) ──────────────────────┐                     │
 016 + 020 ─ 021 ─ 022 ─ 023 ─ 024 ─ 025 ─ 026 ─ 027 ─ 029 ◀───────┘
                                          026 ─ 039 ─┐   027 ─ 040
 016 ─ 030 ─ 031 ─┬─ 032 (+012)                       ├─ 045 ─ 046 ─ 047, 050
                  └─ 033 ─ 034 ─ 035 ─ 036 ─ 037      │
 029 + 042 ─ 043;  042 + 028 ─ 044 ─ 049 (+048), 057, 058
 028 + 032 ─ 051 ─ 052, 053, 054 ─ 060 ─ 062
```

Критический путь MVP: 001 → 003 → 004 → 005 → 006 → 013 → 015 → 016 → 021 → 023 → 024 → 025 →
026 → 027 → 029 (+ 007…010, 028 параллельно) → frontend 033…037.

Что можно вести параллельно (разные файлы, нет общей миграции в одном коммите):
- **IC-020 (политики)** — сразу, зависит только от готовых моделей.
- **IC-002, IC-011, IC-012** — параллельно с IC-005…IC-008.
- **Docker-ветка (007–010)** и **пользователи (013–015)** — после IC-006.
- **Frontend-каркас (030–031)** — как только есть хоть один API (после IC-016); экраны догоняют backend по одному.
- **outbox (042)** и **напоминания-модель (048)** — сразу после IC-006, независимо от идей/голосов.
- **Скрипты эксплуатации (055, 056)** — после IC-008/009.
- Ограничение: миграции Alembic линейны — задачи с миграциями (013, 021, 023, 026, 042, 048) сливать
  последовательно, иначе конфликт `down_revision` (при параллельной работе — ребейз и перегенерация ревизии).

---

## 4. Технические риски

| # | Риск | Влияние | Смягчение |
|---|---|---|---|
| Т-1 | Среда проверки: на Mac владельца нет Python 3.12/uv, Docker Desktop не проверен; в облачном контейнере агента есть docker-клиент, uv, node 22, python3.12, psql — но демон Docker и запуск postgres не проверены | integration/e2e нельзя доказать, Р14 (БД `ideas_test` в compose `db` на :5433) не выполнится | В IC-001/IC-008 первым делом проверить `docker info`/`compose up db`; запасной путь для агента — postgres из CI или локальный `postgres` в контейнере агента (записать как допущение); CI как основной доказатель |
| Т-2 | `run_in_transaction` с повтором + savepoint-изоляция тестов: повтор внутри внешней тестовой транзакции ведёт себя иначе (после ошибки нужен откат к savepoint) | ложнозелёные тесты гонок | Все тесты гонок и повторов — маркер `commits` (реальные commit + TRUNCATE), отдельные соединения |
| Т-3 | Порядок «lock → миграции»: Alembic в `entrypoint.sh` как отдельный процесс не держит lock процесса uvicorn | окно, когда второй экземпляр мигрирует под работающим app | Запускать миграции программно (`alembic.command.upgrade`) из того же процесса после захвата lock, до старта uvicorn-сервера (или один python-лаунчер, держащий соединение с lock и затем запускающий `uvicorn.Server`). Требует решения в IC-009 |
| Т-4 | Монотонность часов: корректность «голос до дедлайна попадает в итог» (Р6) опирается на то, что `now` финализации ≥ `now` любого принятого раньше голоса; скачок системных часов назад (NTP) ломает это | редкое расхождение итога | Один процесс — одни часы; финализация делает `FOR UPDATE` и ждёт записи; принять как остаточный риск, записать |
| Т-5 | Конкуренция `FOR SHARE` у каждой записи и `FOR UPDATE` финализации при `lock_timeout=2s` | финализация может падать по lock timeout в пике голосования у дедлайна | Задача идемпотентна, повторится на следующем тике; лог `job`; int-тест «финализация после lock timeout» |
| Т-6 | E2E: тестовые часы только вперёд, одна БД `ideas_e2e`, тик раз в 15 с | медленные/флейки тесты писем и финала; состояние между прогонами | Пересоздавать `ideas_e2e` в начале `make e2e`; после сдвига часов выполнять тик синхронно (IC-051); каждый тест создаёт свой конкурс |
| Т-7 | `exactOptionalPropertyTypes` + сгенерированные `openapi-typescript` типы + openapi-fetch | трение при типизации, соблазн ручных типов | Проверить на IC-031 до написания экранов; при несовместимости — запись в §17 и ослабление опции только для `schema.gen.ts` |
| Т-8 | Стабильность снимка OpenAPI (порядок ключей, версии FastAPI/Pydantic) | шумный diff в CI | Фиксированные версии в `uv.lock`, сортировка ключей при экспорте |
| Т-9 | Rate limiter и шина в памяти, `uvicorn --reload` в dev | `--reload` запускает дочерний процесс; lock и шина живут в нём — ок, но перезапуск сбрасывает лимиты | Записано как остаточный риск (есть в edge-cases) |
| Т-10 | Argon2id m=19 МиБ × семафор 4 при `mem_limit 512m` вместе с пулом и Node-сборкой не в рантайме | OOM при пиках входов | int-тест 10 одновременных входов (IC-014) |
| Т-11 | Ловушка CSRF/Origin и WS через Vite-прокси в dev (`changeOrigin`, `ws: true`) | фронтенд-разработка «не работает» → желание отключить проверку | Явно настроить прокси в IC-031, `:5173` в `ALLOWED_ORIGINS` только dev |
| Т-12 | Одно большое решение «events after commit» во всех сервисах (IC-045) затрагивает 4 модуля | крупный MR | Ввести `EventPublisher` с no-op реализацией уже в IC-024/026 (допущение), в IC-045 только подменить реализацию |

---

## 5. Противоречия в CLAUDE.md и открытые технические вопросы

### Противоречия (требуют правки документа в соответствующей задаче)

| # | Где | Суть | Предложение |
|---|---|---|---|
| П-1 | §4.2 граф межмодульных зависимостей | `reminder` зависит только от `contest`, но выбор «кто не участвовал» требует данных `idea` и `vote` (§7.2: `NOT EXISTS(участие)`). Аналогично `idea` (список с `my_vote`) нуждается в `vote`, а граф ставит `vote` выше `idea` | `reminder` поставить над `vote` (`vote ← reminder`). `my_vote` собирать в сервисе более высокого слоя (vote.service обогащает список) или формировать список идей для фазы голосования в `vote`. **Требует обсуждения** |
| П-2 | §4.2 / §8.2 / §9.2 | `app.realtime` «не импортирует предметные модули», но `realtime/model/policy.py::event_recipients` должен знать фазу (`ContestPhase`) и автора идеи; WS-контроллер нуждается в `auth.service` для сессии | Публикующий сервис сам вычисляет аудиторию (`Audience.ALL / ORGANIZERS / USERS{ids}`), realtime только рассылает; WS-controller получает actor через `core`-зависимость, предоставленную `auth` (инверсия) или разрешённым исключением. **Требует обсуждения** |
| П-3 | §8.2 `GET /api/contests/{id}` → `allowed_actions` | Карточка конкурса в модуле `contest` (нижний слой) не может импортировать политики `idea`/`vote`/`result` | Политики уровня конкурса (`can_submit_ideas`, `can_vote_in_contest`, `can_view_results`) — в `contest/model/policy.py`; поэлементные — в модулях идей/голосов (заложено в IC-020) |
| П-4 | §7.1 колонка «Владелец», §7.1 «`domain.ranking.rank_ideas`», §10.3 «`app/domain`, `app/security` ≥ 95 %», edge-cases «`domain.policies`», §1/edge-cases `compute_phase` | Остатки старой структуры (Р2 до 05:35) и старых имён; в коде `ContestSchedule.phase_at` | Обновить на `result/model/ranking.py`, `*/model/policy.py`, порог покрытия — для `app/*/model` и `auth/service/password`; `compute_phase` → `phase_at` |
| П-5 | §8.2 / edge-cases vs код | Контракт: 422 `deadlines_order`; код: `InvalidContestError.code = "invalid_contest"` для порядка дедлайнов (и темы/описания одновременно) | Отдельное исключение `DeadlinesOrderError(code="deadlines_order")` (IC-021) |
| П-6 | §1 П2 «FakeClock» vs §10.1 «FrozenClock» | Два имени одного тестового класса | Одно имя (`FrozenClock`) |
| П-7 | §4.3 «Отправка SMTP — notification/handler (тик и событие «есть письма»)» + «notification не импортирует предметные модули» | Событие «есть письма» — через шину `realtime`? Тогда notification зависит от realtime | Пробуждение отправщика — собственный `asyncio.Event` в `notification.service`, без шины (заложено в IC-044) |
| П-8 | §7.4 «сначала lock, затем миграции» vs §2.3/runbook «миграции в entrypoint» | Shell-entrypoint не может удерживать lock на время миграций и сервера | См. Т-3: python-лаунчер (IC-009) |
| П-9 | §2.3 | Этап 3 «удалить `main.py`», но `main.py` вне git — коммит этого не сделает | Удаление на Mac владельца вручную, отметка в README |
| П-10 | §2.1 / §6.1 | Проверка шла `python3 -m pytest` (3.13) без uv и lock-файла; ruff `banned-api` (`TID251`), `pytest-randomly`, `hypothesis` в pyproject нет, хотя §6.2/§10.3 их требуют | IC-001 |
| П-11 | §16 | Нумерация пунктов 5, 7, 6 | Косметика |
| П-12 | §8.2 события | Тип `phase_changed` есть, но никто его не публикует: смена фазы вычисляется, клиент перечитывает сам (§3.2 п. 4) | Публиковать `phase_changed` (допущение) из тика финализации (итоги готовы) — или убрать тип. **Требует обсуждения** |
| П-13 | §7.1 `contests` | CHECK длин темы/описания не перечислены, хотя в модели есть лимиты | Добавить CHECK в миграцию IC-021 |

### Открытые технические вопросы и допущения

| # | Вопрос | Допущение (пока нет решения) |
|---|---|---|
| О-1 | Входит ли пользователь автоматически после регистрации? | Да, `register` создаёт сессию (меньше шагов в e2e). **Допущение** |
| О-2 | Может ли организатор удалять идеи/конкурсы, отменять конкурс? | Нет (ТЗ не требует; Р13). **Допущение** |
| О-3 | Как e2e дождаться финализации/напоминаний без 15-секундного тика? | `POST /api/__test__/clock` после сдвига синхронно выполняет тик. **Допущение**, нужно записать в §8.2 |
| О-4 | Нужен ли `GET` одной идеи (`/api/ideas/{id}`) для правки? | Нет, достаточно списка. **Допущение** |
| О-5 | `voters_count` на дашборде — люди с текущими голосами или когда-либо голосовавшие? | С текущими голосами (согласуется с толкованием «не участвовал»). **Допущение** |
| О-6 | В каком поясе организатор вводит дедлайн в UI? | Пояс браузера, отправка ISO со смещением; `DISPLAY_TZ` — только для писем. **Допущение** |
| О-7 | Нужна ли миграция «данные демо» или `SEED_DEMO` в коде? | В коде (CLI/lifespan), не в миграции. **Допущение** |
| О-8 | Где агент гоняет integration/e2e (см. Т-1)? | В облачном контейнере через docker, если демон доступен; иначе CI. **Требует проверки** |
| О-9 | Порядок MR: один MR на этап или на модуль? | MR на каждую строку колонки «MR» таблицы §1; коммит на задачу. **Требует согласования с владельцем** |
| О-10 | Порог покрытия ветвей ≥95 % — для каких пакетов после смены структуры? | `app/*/model` + `auth/service/password.py`. **Допущение** |
