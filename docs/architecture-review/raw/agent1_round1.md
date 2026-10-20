# Агент 1 — Architecture & Maintainability (раунд 1)

Статус: предложение, кода нет, ничего не запускалось. Фактическое состояние — по facts.md (исходников нет). Всё ниже «предлагаемое», если не помечено иначе.

## 0. Что сохраняю из черновика и что меняю

Сохраняю (обосновано и сверено с ТЗ): вычисляемая фаза (П1/П2); инварианты в БД (UNIQUE голосов, CASCADE); outbox + Mailpit; серверные сессии в cookie; часы как зависимость; tie-break `votes DESC, submitted_at ASC, id ASC`; Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + asyncpg; React + TS + Vite + TanStack Query; Playwright с двумя контекстами; имена полей `submission_deadline`/`voting_deadline` (не переименовываю ради стиля).

Меняю:
1. **Frontend в отдельном nginx-контейнере (§2, О1 черновика) противоречит инварианту «один контейнер приложения».** Предлагаю multi-stage образ: стадия Node собирает SPA, Python-стадия отдаёт `dist/` через FastAPI. Frontend остаётся отдельным кодом, сборкой, тестами и общается с backend только по HTTP/WS — О1 выполняется на уровне архитектуры, не на уровне числа контейнеров (см. риск R1).
2. **LISTEN/NOTIFY → внутрипроцессная шина событий.** Обоснование черновика «работает при нескольких процессах» снято инвариантом (одна реплика, один worker uvicorn). LISTEN требует выделенного соединения и переподключения — лишняя сложность. Шина за интерфейсом, заменима на NOTIFY за один модуль.
3. **WS-события — только сигналы инвалидации без данных** (`{type, contest_id, idea_id?}`); данные клиент перечитывает через REST. Авторизация и анонимность живут в одном месте (REST-сериализация), в WS нечему утечь.
4. **Плоские `models.py`/`schemas.py` → слои с явным направлением зависимостей** и автоматической проверкой (import-linter).
5. **Формат ошибок `{"detail": "..."}` → problem+json с машинным `code`**: фронту нужно различать «приём закрыт» и «устаревшая версия» при одном статусе 409.
6. Добавляю: optimistic locking для правки идеи, `Idempotency-Key` для создания идеи, `/api/v1`, `allowed_actions` в ответе (правила не дублируются в TS), контроль дрейфа OpenAPI-контракта.

## 1. Доменная модель и глоссарий

Единая терминология в коде, API, UI-текстах и документации:

| RU | EN (код/API) | Значение |
|----|--------------|----------|
| конкурс | `contest` | тема + два дедлайна |
| раунд | `round`: `submission` \| `voting` | период приёма/голосования (для напоминаний) |
| фаза | `phase`: `submission` \| `voting` \| `finished` | вычисляется из `now` и дедлайнов |
| идея | `idea` | title, description, author |
| голос | `vote` | (idea, voter), не более одного |
| организатор / сотрудник | `organizer` / `employee` | роли |
| автор / голосующий | `author` / `voter` | роли пользователя относительно идеи |
| финализация | `finalization` | разовая фиксация итогов и постановка писем |

Агрегаты и владельцы данных (одна служба-владелец на запись):

| Сущность | Владелец записи (модуль services) | Инварианты | Где держится |
|----------|-----------------------------------|-----------|--------------|
| User, Session | `auth` | уникальный login/email; токен хранится хэшем | БД UNIQUE |
| Contest | `contests` | `submission_deadline < voting_deadline`; дедлайны в будущем при создании | БД CHECK + домен |
| Idea | `ideas` | создание/правка только в `submission`; удаление в `submission`/`voting`; `submitted_at` неизменен | домен + сервис; БД NOT NULL |
| Vote | `votes` | один на (idea, voter); не за свою; только в `voting` | БД UNIQUE + сервис |
| Reminder | `reminders` | одно на (contest, round, user) | БД UNIQUE |
| OutboxEmail | `mail` (запись — сервисы, отправка — `jobs`) | одно письмо на `dedup_key` | БД UNIQUE |
| Finalization | `finalization` | `finalized_at` ставится один раз | `UPDATE ... WHERE finalized_at IS NULL` |

Результаты — **не хранятся**, считаются запросом `COUNT ... GROUP BY` (нет денормализованных счётчиков → нет потерянных обновлений). При тысячах голосов это миллисекунды.

ID: `bigint GENERATED ALWAYS AS IDENTITY`. Причина: простота, монотонность для tie-break. Альтернатива UUIDv7 — не нужна (нет распределённой генерации, порядок подачи и так публичен по правилу ничьей). Ограничение: ID перечислимы → объектная авторизация обязательна на каждом запросе (она и так обязательна). Проверка: интеграционные тесты «чужой ID → 404».

## 2. Модули backend и направление зависимостей

### Решение
Слоистый монолит, один процесс, четыре слоя:

```
entrypoints:  app.api (HTTP/WS)      app.jobs (планировщик)      app.cli
                    │                       │                       │
                    └──────────┬────────────┴───────────────────────┘
                               ▼
use cases:               app.services        (транзакции, авторизация объектов, события, outbox)
                               │
          ┌────────────┬───────┼──────────┬─────────────┐
adapters: app.db    app.mail  app.realtime  app.security   (I/O и технические детали)
          └────────────┴───────┼──────────┴─────────────┘
                               ▼
pure:                     app.domain        (фазы, правила, ранжирование, доменные ошибки; без I/O)
                               ▲
shared:                   app.core          (config, clock, logging, базовые ошибки) — импортируется всеми, кроме domain
composition root:         app.main          (собирает всё; единственный, кто импортирует все слои)
```

**Причина.** Бизнес-правила ТЗ (фазы, видимость, ничья, «не за свою», «кто не участвовал») тестируются как чистые функции без БД и часов; транспорт (FastAPI) и хранилище (SQLAlchemy) заменяемы и не протекают в правила.
**Альтернативы.** (а) Плоская структура черновика — дешевле на старте, но правила расползаются по роутерам, проверить границы нечем. (б) Hexagonal с портами на каждый репозиторий и Unit of Work — для 6 таблиц лишние абстракции. (в) Vertical slices (`features/ideas/{api,service,db}`) — хорошо при многих фичах, но правила фаз общие для idea/vote, их пришлось бы выносить всё равно.
**Ограничения.** Без интерфейсов репозиториев: сервисы работают с `AsyncSession` и функциями запросов из `app.db.queries`. Интерфейсы (Protocol) — только там, где нужна подмена в тестах без сети: `Clock`, `EmailSender`, `EventPublisher`.
**Проверка.** import-linter в CI (`lint-imports`):

```ini
# backend/.importlinter
[importlinter]
root_package = app
[importlinter:contract:layers]
name = Слои
type = layers
layers =
    app.main
    app.api | app.jobs | app.cli
    app.services
    app.db | app.mail | app.realtime | app.security
    app.domain
[importlinter:contract:domain-pure]
name = Домен без инфраструктуры
type = forbidden
source_modules = app.domain
forbidden_modules = sqlalchemy, fastapi, starlette, pydantic, asyncpg, app.core.config, app.core.clock
[importlinter:contract:services-no-http]
name = Сервисы не знают про HTTP
type = forbidden
source_modules = app.services
forbidden_modules = fastapi, starlette
[importlinter:contract:adapters-independent]
name = Адаптеры не зависят друг от друга
type = independence
modules = app.db, app.mail, app.realtime, app.security
```

`app.core` не включён в layers, но домену запрещён (кроме `app.core.errors`, если понадобится). Циклов нет по построению; дополнительно `ruff` правило `TID252` (запрет относительных импортов выше пакета).

### Точки входа и владельцы побочных эффектов
| Побочный эффект | Единственный владелец |
|-----------------|-----------------------|
| Транзакция БД (begin/commit) | функция сервиса (`async with session.begin()`) |
| Публикация WS-события | сервис, **после** commit |
| Постановка письма | сервис, **внутри** транзакции (запись в outbox) |
| Отправка SMTP | `jobs.outbox_dispatcher` → `mail.SmtpEmailSender` |
| Чтение времени | `core.clock.Clock`; домен получает `now` аргументом |
| Финализация, напоминания | `jobs.scheduler` вызывает `services.finalization` / `services.reminders` |
| Маппинг ошибок в HTTP | `api.errors` (exception handlers) |

## 3. Дерево каталогов

```
IdeasCompetition/
├── CLAUDE.md  README.md  Makefile  docker-compose.yml  .env.example  .gitignore
├── Dockerfile                    # multi-stage: node build SPA → python runtime (+ dist в /app/static)
├── docs/  (prompts.md, agent-session/, adr/ — опционально)
├── tools/export_agent_session.py
├── backend/
│   ├── pyproject.toml  uv.lock  .python-version (3.12)  alembic.ini  .importlinter
│   ├── migrations/  (env.py, versions/)
│   ├── app/
│   │   ├── main.py               # create_app(), lifespan: engine, scheduler, bus; монтирует SPA
│   │   ├── core/   config.py (pydantic-settings, валидация при старте) clock.py logging.py errors.py
│   │   ├── domain/
│   │   │   ├── phase.py          # Phase, compute_phase(), round_closing_at()
│   │   │   ├── policies.py       # allowed_actions(), can_view_authors(), ensure_can_vote() …
│   │   │   ├── ranking.py        # rank_ideas(), pick_winner()
│   │   │   ├── reminders.py      # reminder_due(), select_recipients() (кто не участвовал)
│   │   │   ├── types.py          # frozen dataclasses: ContestSchedule, IdeaScore, Actor
│   │   │   └── errors.py         # DomainError(code) + SubmissionClosed, VotingClosed, OwnIdeaVote, StaleVersion …
│   │   ├── services/  auth.py contests.py ideas.py votes.py results.py finalization.py reminders.py
│   │   ├── db/
│   │   │   ├── engine.py         # create_engine, session factory, таймауты
│   │   │   ├── models.py         # ORM-таблицы (одна точка; разбить при >~300 строк)
│   │   │   ├── queries/  users.py contests.py ideas.py votes.py outbox.py
│   │   │   └── errors.py         # IntegrityError → доменные/технические ошибки
│   │   ├── security/  passwords.py (argon2) tokens.py (secrets+sha256) origin.py (CSRF/WS Origin)
│   │   ├── realtime/  bus.py (EventPublisher, in-process) hub.py (WS-подписки по contest_id)
│   │   ├── mail/      sender.py (EmailSender Protocol, SmtpEmailSender) templates.py
│   │   ├── jobs/      scheduler.py (цикл + pg_advisory_lock) outbox_dispatcher.py
│   │   ├── api/
│   │   │   ├── deps.py           # get_session, get_clock, current_user, require_organizer
│   │   │   ├── errors.py         # problem+json handlers
│   │   │   ├── spa.py            # StaticFiles + fallback index.html для не-/api путей
│   │   │   ├── routers/  health.py auth.py contests.py ideas.py votes.py organizer.py events_ws.py
│   │   │   └── schemas/  auth.py contests.py ideas.py results.py errors.py
│   │   └── cli.py                # create-organizer, seed-demo, export-openapi
│   └── tests/
│       ├── unit/          # domain/*, без БД и сети
│       ├── integration/   # services+db на реальном PostgreSQL, миграции
│       ├── api/           # HTTP-контракт через httpx.AsyncClient, коды и формы ошибок
│       ├── fakes.py       # FakeClock, RecordingEmailSender, RecordingPublisher
│       └── conftest.py
├── frontend/
│   ├── package.json  package-lock.json  .nvmrc (22)  vite.config.ts  tsconfig.json
│   ├── eslint.config.js  .prettierrc  .dependency-cruiser.cjs
│   └── src/
│       ├── main.tsx
│       ├── app/        App.tsx router.tsx queryClient.ts
│       ├── api/        schema.gen.ts (из OpenAPI) client.ts (openapi-fetch + ApiError) queryKeys.ts events.ts (WS + reconnect → invalidate)
│       ├── features/   auth/ contests/ ideas/ voting/ results/ organizer-dashboard/
│       ├── pages/      LoginPage ContestListPage ContestPage OrganizerDashboardPage NotFoundPage
│       ├── shared/     ui/ lib/serverTime.ts lib/format.ts
│       └── test/       msw-handlers.ts setup.ts
└── e2e/   package.json  playwright.config.ts  tests/  (два контекста браузера)
```

Почему `app/` а не src-layout: так в черновике, переименование ничего не даёт. Почему один Dockerfile в корне: ему нужны и `frontend/`, и `backend/` в контексте сборки.

## 4. Компоненты и потоки данных

```
 Браузер (вкладка A, B)                    Контейнер app (1 процесс uvicorn, workers=1)
 ┌──────────────────────┐  HTTPS /api/v1  ┌──────────────────────────────────────────┐
 │ SPA (React)          │ ──────────────▶ │ api → services → domain                  │
 │ TanStack Query cache │ ◀────────────── │            │ db (asyncpg pool) ──────────┼──▶ PostgreSQL (контейнер db)
 │ events.ts (WS)       │ ◀── WS сигналы ─│ realtime.hub ◀─ bus ◀─ services (после commit)
 └──────────────────────┘                 │ jobs.scheduler (тик N с) → services       │
       ▲ GET / → index.html, /assets      │ jobs.outbox_dispatcher → mail ────────────┼──▶ Mailpit (контейнер mail)
                                          └──────────────────────────────────────────┘
```

Основные потоки:
1. **Подача/правка идеи.** `POST /contests/{id}/ideas` → `services.ideas.submit_idea(session, clock, actor, contest_id, data, idempotency_key)`: `now = clock.now()`; в транзакции `SELECT contest FOR SHARE` → `domain.policies.ensure_can_submit(schedule, now, actor)` → INSERT → commit → `bus.publish(IdeasChanged(contest_id))`. Момент приёма = `now`, прочитанный внутри транзакции. FOR SHARE (не FOR UPDATE) — дедлайны не меняются конкурентно, достаточно защиты от удаления конкурса; голоса не сериализуются.
2. **Голос.** `PUT /ideas/{id}/vote` → `votes.cast_vote`: проверить фазу, «не своя», `INSERT ... ON CONFLICT DO NOTHING` → 204 в обоих случаях (идемпотентно). FK-нарушение (идею удалили параллельно) → `IdeaNotFound` → 404. Событие `ResultsChanged` (получает только организатор).
3. **Удаление идеи в голосовании (П11).** DELETE → CASCADE голосов в той же транзакции → после commit `IdeaDeleted(contest_id, idea_id)` всем подписчикам конкурса → клиенты удаляют идею из кэша и перечитывают список.
4. **Экран организатора (П7).** REST `GET /organizer/contests/{id}/dashboard` + WS; на `ResultsChanged`/`IdeasChanged` — refetch с throttle 1 с на клиенте.
5. **Смена фазы.** Фазу никто не «переключает». Клиент получает `server_time` и дедлайны, планирует refetch на момент дедлайна по серверному смещению; планировщик дополнительно шлёт `PhaseChanged` на первом тике после дедлайна. Даже без событий сервер отклонит запоздавшую запись (П2).
6. **Финал и письма.** Тик → `finalization.finalize_due_contests(now)`: `UPDATE contests SET finalized_at=now WHERE voting_deadline<=now AND finalized_at IS NULL RETURNING id` + outbox-записи в той же транзакции. Отдельно `outbox_dispatcher` отправляет pending с ограниченными попытками.
7. **Напоминания (П9).** Тик → `reminders.enqueue_due_reminders(now)`: домен выбирает раунды, у которых `deadline-24h <= now < deadline`, и неучаствовавших; INSERT в `reminders ON CONFLICT DO NOTHING RETURNING` → outbox только для реально вставленных.

**Решение по реалтайму:** WS-сигналы инвалидации, in-process шина.
Причина: одна реплика по инварианту; сигналы без данных не требуют авторизации полезной нагрузки (кроме фильтра «ResultsChanged только организатору»). Альтернативы: SSE (подошло бы, но WS в черновике и FastAPI поддерживает нативно; SSE проще проксировать — оставить как запасной вариант), LISTEN/NOTIFY (нужен при >1 процессе), polling (нарушает дух П7). Ограничения: событие теряется, если процесс упал между commit и publish, и при разрыве WS → клиент при переподключении делает полный refetch; при `workers>1` шина перестаёт работать — поэтому `workers=1` зафиксирован в config и проверяется при старте. Проверка: интеграционный тест с `RecordingPublisher` (событие только после commit, нет события при rollback); e2e с двумя контекстами.

## 5. Контракт API

**Версионирование.** Префикс `/api/v1`. SPA и backend выкатываются одним образом, поэтому несовместимость возможна только у вкладки, открытой до перезапуска: backend отдаёт `X-App-Build` в каждом ответе и в WS `hello`; клиент при расхождении показывает «Доступна новая версия — обновите страницу». `/api/v2` вводится только при появлении внешних клиентов.

**Источник контракта.** OpenAPI, генерируемый FastAPI из Pydantic-схем. `make contract` → `python -m app.cli export-openapi > frontend/openapi.json` → `openapi-typescript` → `frontend/src/api/schema.gen.ts` (коммитится). CI: регенерировать и `git diff --exit-code`. Ручных TS-типов ответов API нет.

**Эндпоинты** (уточнение черновика):

| Метод и путь | Кто | Успех | Ошибки (code) |
|---|---|---|---|
| POST /auth/register, /auth/login, /auth/logout; GET /auth/me | все/вошедший | 201/200/204/200 | 422, 401 `INVALID_CREDENTIALS`, 409 `LOGIN_TAKEN`, 429 |
| GET /contests?limit&offset | вошедший | 200 `{items,total}` | — |
| POST /contests | организатор | 201 + Location | 422 `DEADLINES_ORDER`, 403 |
| GET /contests/{id} | вошедший | 200 `{…, phase, server_time, allowed_actions, tie_break_rule}` | 404 |
| GET /contests/{id}/ideas | вошедший | 200: submission — только свои; voting — все без автора + `is_mine`; finished — с авторами | 404 |
| POST /contests/{id}/ideas (Idempotency-Key) | сотрудник | 201 | 409 `SUBMISSION_CLOSED`, 403 `ORGANIZER_CANNOT_PARTICIPATE` |
| PATCH /ideas/{id} (поле `version`) | автор | 200 | 409 `SUBMISSION_CLOSED`/`STALE_VERSION`, 404 |
| DELETE /ideas/{id} | автор | 204 | 409 `IDEA_LOCKED` (finished), 404 |
| PUT/DELETE /ideas/{id}/vote | сотрудник | 204 (идемпотентно) | 409 `VOTING_CLOSED`, 403 `OWN_IDEA_VOTE`, 404 |
| GET /contests/{id}/results | все после финала | 200 ранжированный список с авторами и `is_winner` | 403 `RESULTS_NOT_PUBLISHED` |
| GET /organizer/contests/{id}/dashboard | организатор | 200 `{ideas_count, voters_count, results[]}` | 403 |
| WS /contests/{id}/events | вошедший | `{"v":1,"type":"idea_deleted"|"ideas_changed"|"phase_changed"|"results_changed",…}` | close 4401/4403 |
| GET /health/live, /health/ready | все | 200 / 503 | — |

`allowed_actions` (например `{"submit_idea":true,"vote":false,"view_results":false}`) вычисляет `domain.policies` — фронт не повторяет правила фаз, только отображает. Это главный приём против дрейфа логики между Python и TS.

**Формат ошибки** (RFC 9457, `application/problem+json`):
```json
{"type":"about:blank","title":"Приём идей закрыт","status":409,
 "code":"SUBMISSION_CLOSED","detail":"Приём идей закрылся 2026-11-01T12:00:00Z",
 "request_id":"01J…","errors":[{"field":"title","code":"too_long"}]}
```
Правила: `code` — стабильный UPPER_SNAKE из `domain.errors`/`api.errors`, фронт ветвится только по нему; `title` — понятный пользователю текст; 500 → `INTERNAL_ERROR` без стека и SQL; 422 FastAPI переупаковывается в тот же формат.

**Коды:** 400 — неверный JSON; 401 — нет/истекла сессия; 403 — роль/правило против актора; **404 — объект не существует или недоступен актору** (чужая идея в фазе подачи → 404, не 403, чтобы не раскрывать существование); 409 — конфликт фазы/версии/уникальности; 413 — тело > 64 КБ; 422 — валидация; 429 — лимит входа.

**Пагинация.** Только `GET /contests` (`limit` ≤ 100, `offset`, стабильная сортировка `voting_deadline DESC, id DESC`). Идеи конкурса отдаются целиком: для голосования нужен полный список, объём — сотни. Ограничение: защитный cap 1000 идей в ответе с флагом `truncated` (риск R6). Фильтрация/сортировка на клиенте не делается для результатов — порядок задаёт сервер (правило ничьей).

**Валидация.** Даты — ISO 8601 **обязательно со смещением** (naive → 422), хранение UTC. Строки: NFC-нормализация, trim, запрет управляющих символов; title 1–200, description 1–5000 символов. Лимит тела — middleware.

**Идемпотентность.** PUT/DELETE vote — естественно идемпотентны. POST idea — `Idempotency-Key` (UUID от клиента) хранится в `ideas.idempotency_key`, `UNIQUE(author_id, idempotency_key)`; повтор → 200 с той же идеей. Альтернатива (таблица ключей для всех POST) — избыточна для одного эндпоинта.

## 6. Code style

### Python
| Что | Инструмент | Команда |
|---|---|---|
| Зависимости/версия Python | uv + `uv.lock`, `.python-version` 3.12 (системный 3.9.6 на Mac не используется) | `uv sync --frozen` |
| Формат | ruff format (line-length 100) | `uv run ruff format --check .` |
| Линт | ruff: `E,F,W,I,B,UP,SIM,RUF,DTZ,S,BLE,T20,TID,ASYNC,PT,N,ERA` | `uv run ruff check .` |
| Типы | mypy `--strict` + плагин pydantic | `uv run mypy app tests` |
| Границы | import-linter | `uv run lint-imports` |

Конкретные правила с автопроверкой:
- `DTZ` запрещает naive datetime; `TID251` banned-api: `datetime.datetime.now`, `datetime.datetime.utcnow`, `time.time` → «используйте `Clock`» (разрешено только в `app/core/clock.py` через `per-file-ignores`).
- `BLE001`/`S110`: нет `except Exception: pass`. Широкий `except` допустим только в цикле `jobs.scheduler` с логированием и продолжением.
- `T20`: нет `print`; логирование через `core.logging`.
- Типы выражают состояния: `Phase = Literal["submission","voting","finished"]` или `StrEnum`; `Actor` — frozen dataclass; `Optional` только где NULL осмыслен.
- Функции: глагол + предмет. Предикаты `is_/can_/has_` возвращают `bool` и не бросают; `ensure_*` бросают доменную ошибку и ничего не возвращают; функции с I/O — `async`.

Хорошие имена и размещение:
| Логика | Где | Имя |
|---|---|---|
| Фаза из времени | `domain/phase.py` | `compute_phase(schedule, now) -> Phase` |
| Можно ли голосовать | `domain/policies.py` | `can_vote(...) -> bool`, `ensure_can_vote(...) -> None` |
| Порядок и победитель | `domain/ranking.py` | `rank_ideas(scores) -> list[RankedIdea]` |
| Кому напомнить | `domain/reminders.py` | `select_reminder_recipients(employees, participants)` |
| Голос в транзакции | `services/votes.py` | `cast_vote`, `withdraw_vote` |
| SQL подсчёта | `db/queries/votes.py` | `count_votes_by_idea(session, contest_id)` |
| HTTP-схема | `api/schemas/ideas.py` | `IdeaForVoting` (без поля автора), `IdeaWithAuthor` |
Плохо: `process_vote`, `check_phase` (непонятно: bool или исключение), `utils.py`, `helpers.py`, логика в роутере, `session.commit()` в роутере.

Ошибки: доменные исключения несут `code`; `db/errors.py` переводит `IntegrityError` по имени constraint в доменные (`uq_votes_idea_voter` → идемпотентный успех; `fk_votes_idea` → `IdeaNotFound`); всё неизвестное → 500 с `request_id`, детали только в лог. Комментарии — «почему» (например, почему FOR SHARE, почему 404 вместо 403).

Анонимность закрепляется типами: для фазы voting роутер возвращает `list[IdeaForVoting]`, где поля автора нет физически; `response_model` FastAPI отбрасывает лишнее. Проверка: api-тест, что в JSON фазы voting нет ключей `author*`, и e2e.

### TypeScript
| Что | Инструмент | Команда |
|---|---|---|
| Версия/зависимости | Node 22 LTS (`.nvmrc`), npm + `package-lock.json` | `npm ci` |
| Формат | Prettier | `npm run format:check` |
| Линт | ESLint flat config + typescript-eslint `strictTypeChecked`, react-hooks, jsx-a11y | `npm run lint` |
| Типы | `tsc --noEmit`, `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` | `npm run typecheck` |
| Границы | dependency-cruiser | `npm run depcruise` |
| Тесты | Vitest + Testing Library + MSW | `npm test` |

Правила frontend:
- Слои: `pages → features → api | shared`; `features/*` не импортируют друг друга; `api` не импортирует React-компоненты. `fetch`/`WebSocket` запрещены вне `src/api` (`no-restricted-globals` + `no-restricted-syntax`).
- `@typescript-eslint/no-floating-promises`, `switch-exhaustiveness-check` (по `phase`, `code`, типу события).
- Время: только `shared/lib/serverTime.ts` (смещение от `server_time`) — `Date.now()` прямо запрещён `no-restricted-properties`. Отображение — `Intl.DateTimeFormat` в TZ браузера; ввод организатора `datetime-local` → ISO со смещением.
- Права: кнопки показываются по `allowed_actions`, не по локальной проверке фазы.
- Имена: компоненты `PascalCase` (`VoteButton`), хуки `useCastVote`, query keys в `api/queryKeys.ts` (`contestKeys.ideas(id)`).

Агрегатор: `make check` = format-check + lint + typecheck + lint-imports + depcruise + contract-diff + unit + integration (+ `make e2e` отдельно).

## 7. Где размещать новый код

| Изменение | Куда |
|---|---|
| Новое бизнес-правило (кто/когда может) | `domain/policies.py` + unit-тест на границы; если влияет на UI — поле в `allowed_actions` |
| Новый сценарий записи | функция в `services/<агрегат>.py`, транзакция там же |
| Новый SQL | `db/queries/<агрегат>.py`; миграция Alembic, если схема |
| Новый эндпоинт | `api/routers/<ресурс>.py` + схема в `api/schemas/` + регенерация контракта |
| Новый вид письма | `mail/templates.py` + `dedup_key` формата `<kind>:<contest>:<user>` + постановка из сервиса |
| Новая периодическая задача | функция в `services/`, вызов из `jobs/scheduler.py` (не новый процесс) |
| Новое WS-событие | тип в `realtime/bus.py` + обработчик в `frontend/src/api/events.ts` (+ `v` если несовместимо) |
| Экран | `pages/` + логика в `features/<фича>/` |
| Переиспользуемый UI | `shared/ui/` только после второго использования |

## 8. Допустимые зависимости

Runtime backend (всё): `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `argon2-cffi`, `aiosmtplib` (async SMTP; альтернатива stdlib `smtplib` в `to_thread` — тоже приемлема, на выбор реализации). Логи — stdlib `logging` + JSON-форматтер (structlog не нужен).
Dev backend: `pytest`, `pytest-asyncio` (или `anyio`), `httpx`, `ruff`, `mypy`, `import-linter`, `pip-audit`.
Runtime frontend: `react`, `react-dom`, `react-router`, `@tanstack/react-query`, `openapi-fetch`. UI-кит, state-менеджер, библиотеки дат/форм — **не добавлять** (Intl и controlled-формы хватает).
Dev frontend: `vite`, `typescript`, `openapi-typescript`, `eslint` + плагины, `prettier`, `vitest`, `@testing-library/react`, `msw`, `dependency-cruiser`, `@playwright/test` (в `e2e/`).
Инфраструктура: PostgreSQL 16, Mailpit. **Не добавлять** без доказанной необходимости: Redis, Celery/APScheduler, брокеры, nginx (SPA отдаёт backend), отдельный контейнер frontend.
Правило: новая зависимость = строка в журнале решений (зачем, альтернатива «без неё», лицензия), проверка — ревью diff `pyproject.toml`/`package.json` в DoD.

## 9. Стоимость сопровождения и изменений

| Вероятное изменение | Затрагивает | Стоимость |
|---|---|---|
| Изменить правило ничьей/видимости | `domain/*` + unit-тесты | низкая, без БД |
| Добавить фазу «черновик» (конкурс с датой старта) | `domain/phase.py`, колонка + миграция, `allowed_actions` | средняя; `switch-exhaustiveness-check` найдёт все места в TS |
| Несколько реплик backend | `realtime/bus.py` → LISTEN/NOTIFY; scheduler уже под advisory lock; снять `workers=1` | средняя, локализована; противоречит текущему инварианту |
| Реальная почта вместо Mailpit | конфиг SMTP; `EmailSender` не меняется | низкая |
| SSO вместо паролей | `services/auth`, `security/*`; остальное видит только `Actor` | средняя |

Дорогие места: SQL с `FOR SHARE`/`ON CONFLICT` (покрывать integration-тестами), WS-переподключение на фронте, планировщик (тесты через прямой вызов `services.*` с FakeClock, а не через цикл).

## 10. Риски и открытые вопросы

Риски:
- **R1. О1 «отдельный backend и frontend».** При одном контейнере проверяющий может счесть frontend «не отдельным». Смягчение: отдельный каталог, package.json, сборка, тесты; общение только через сеть; README объясняет связь с инвариантом; dev-режим — Vite dev server + proxy. Нужен ответ владельца (В1).
- **R2. Анонимность.** Утечка автора через: лишнее поле в схеме, WS-payload, порядок/ID, текст ошибки, экран организатора до финала. Смягчение: отдельные схемы по фазе, WS без данных, api-тест на отсутствие ключей `author*`.
- **R3. Граница дедлайна.** Запрос, прочитавший `now` до дедлайна и закоммитивший после, принимается. Определение «момента приёма» = `clock.now()` внутри транзакции; фиксируется в документе и тесте. Расхождение часов app vs DB — время берётся только из app.
- **R4. Потеря WS-событий** (commit без publish, разрыв сети) — компенсируется refetch при reconnect и при фокусе вкладки; e2e на reconnect.
- **R5. Одна шина в процессе** ломается при `workers>1` или втором контейнере; проверка конфигурации при старте + инвариант Docker.
- **R6. Список идей без пагинации** — cap и флаг `truncated`; при росте — keyset.
- **R7. Дрейф контракта TS/Python** — генерация типов + diff в CI.
- **R8. Python 3.9.6 на Mac** — без uv/Docker проект не запустится; README «Требования».
- **R9. Письмо «неизвестный результат» SMTP** (таймаут после отправки) → возможный дубль при повторе; at-least-once принимается и документируется.

Открытые вопросы владельцу:
- В1. Приемлем ли один контейнер app с SPA внутри как выполнение О1 (или нужен отдельный контейнер frontend, что меняет инвариант)?
- В2. Видит ли организатор авторов в текущих результатах до финала? (По умолчанию — нет.)
- В3. «Все участники» для финального письма — авторы идей, голосовавшие или все зарегистрированные сотрудники? (По умолчанию — авторы и голосовавшие.)
- В4. Может ли автор удалить идею в фазе подачи и подать заново (влияет на `submitted_at` и ничью)? (По умолчанию — да, новая идея получает новое время.)
- В5. Порядок идей при голосовании: по времени подачи или перемешанный на пользователя (влияние порядка на голосование)?
- В6. Нужна ли правка/удаление конкурса организатором после создания? (По умолчанию — нет: меняет дедлайны под открытыми вкладками.)
- В7. Голос за идею без лимита на число голосов от человека в конкурсе («один голос на идею») — подтвердить, что можно голосовать за все чужие идеи.
