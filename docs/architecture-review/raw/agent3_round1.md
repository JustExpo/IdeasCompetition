# Агент 3 «Data & Operations» — раунд 1

Статус: **только проект**. Все команды ниже — **предлагаемые, никем не запускались**. Кода, Docker, миграций нет (facts.md). Формат решения: **Р** решение → **П** причина → **А** альтернативы → **О** ограничения → **Пр** проверка.

## 0. Критика черновика (что сохранить / исправить)

| Черновик | Оценка | Изменение |
|---|---|---|
| Фаза вычисляется из времени; уникальность/каскады в БД; часы как зависимость; outbox | Сохранить | Уточнено ниже |
| `frontend` отдельным контейнером с nginx | Противоречит допущению 1 и инварианту §9 | Один контейнер `app`: multi-stage сборка SPA, backend отдаёт статику. Код frontend отдельный, общение по HTTP — О1 выполнено |
| «LISTEN/NOTIFY работает при нескольких процессах backend» | Противоречит инварианту | Несколько процессов запрещены; LISTEN/NOTIFY не нужен (§4) |
| «advisory lock гарантирует одного исполнителя» | Неверно как гарантия: session-lock на соединении из пула теряется/утекает | Корректность — условный `UPDATE` и уникальные ключи; advisory lock — оптимизация |
| «два экземпляра не отправят письмо дважды» | Неверно: SMTP даёт только at-least-once | Честная формулировка в §3.3 |
| `votes.id`, `reminders.round` без CHECK, outbox без статуса/аренды | Слабо | Схема §1 |
| «Запуск: `docker compose up --build`» | Нет защиты от конкурентного запуска и чужих экземпляров | `make up` → `scripts/up.sh` (§5) |
| «Под блокировкой строки конкурса» | Не указан тип блокировки и момент чтения часов | §2.2 |

## 1. Схема данных (PostgreSQL 16)

**Р** PK `bigint GENERATED ALWAYS AS IDENTITY`; все времена `timestamptz` (мкс), сессия БД `timezone=UTC`; NOT NULL по умолчанию, NULL только с явным смыслом. **П** просто, компактно, `id` даёт детерминированный tie-break. **А** UUID — скрывает порядок/число записей, но второй ключ для tie-break. **О** id идеи раскрывает порядок подачи (не автора) — принятый риск, см. §10. **Пр** integration-тесты на каждое ограничение (нарушение → ожидаемый код ошибки → понятный ответ API).

| Таблица | Ключевые поля | Ограничения / индексы |
|---|---|---|
| `users` | login, name, email, password_hash, role, is_active, created_at | `UNIQUE(lower(login))`, `UNIQUE(lower(email))`, `CHECK role IN ('employee','organizer')`, длины |
| `sessions` | token_hash bytea PK, user_id, created_at, expires_at, revoked_at NULL | FK users ON DELETE CASCADE; idx(user_id), idx(expires_at) |
| `contests` | topic, description, submission_deadline, voting_deadline, created_by, created_at, finalized_at NULL, winner_idea_id NULL | `CHECK submission_deadline < voting_deadline`; `CHECK (winner_idea_id IS NULL OR finalized_at IS NOT NULL)`; idx(voting_deadline) WHERE finalized_at IS NULL |
| `ideas` | contest_id, author_id, title, description, submitted_at, updated_at, client_request_id uuid | FK contests RESTRICT, users RESTRICT; `CHECK length(btrim(title)) BETWEEN 1 AND 200`, `CHECK length(description) <= 10000`; `UNIQUE(author_id, client_request_id)`; idx(contest_id, submitted_at, id) |
| `votes` | **PK(idea_id, voter_id)**, created_at | FK ideas **ON DELETE CASCADE**, users RESTRICT; idx(voter_id) |
| `reminders` | **PK(contest_id, round, user_id)**, created_at | `CHECK round IN ('submission','voting')`; FK CASCADE от contests |
| `outbox_emails` | dedup_key, kind, user_id NULL, to_email, subject, body NULL, status, attempts, next_attempt_at, lease_until NULL, not_after NULL, last_error NULL, created_at, sent_at NULL | `UNIQUE(dedup_key)`; `CHECK status IN ('pending','sending','sent','failed','expired')`; idx(next_attempt_at) WHERE status IN ('pending','sending') |

NULL-семантика: `finalized_at IS NULL` — финал не выполнен; `finalized_at` есть и `winner_idea_id IS NULL` — идей не было; `revoked_at` — выход; `not_after` — письмо теряет смысл после этого момента (напоминание после дедлайна). Нет nullable-колонок в уникальных ключах (кроме `client_request_id`, где NULL = «клиент не дал ключ», дубли NULL допустимы осознанно).

`submitted_at` ставится один раз при создании, правка меняет только `updated_at` (П10). Победитель: `ORDER BY votes DESC, submitted_at ASC, id ASC`.

**Владельцы данных:** `users/sessions` — модуль auth; `contests/ideas/votes` — домен конкурса; `reminders/outbox` — модуль уведомлений (пишет в общей транзакции с доменом через его репозиторий, читает только сам).

## 2. Время, транзакции, конкурентность

### 2.1 Источник времени
**Р** Источник правды — **часы приложения** (`Clock`, UTC, aware `datetime`). Время берётся один раз на операцию и передаётся в SQL параметром `:now`. `now()` БД допустим только в `server_default` технических `created_at`; в бизнес-предикатах запрещён (проверка: grep в CI по `now()`/`CURRENT_TIMESTAMP` в `app/` кроме моделей).
**П** Тестируемость: `FakeClock` в unit/integration, тестовые часы в e2e (только `APP_ENV=test`); один контейнер приложения = одни часы; контейнеры БД и app на одном ядре (Docker Desktop VM) — расхождения нет.
**А** `now()` БД — единые часы при многих процессах, но время в тестах не перемотать без хаков (GUC, `faketime`); к тому же `now()` = начало транзакции, а не момент решения.
**О** Если когда-то будет >1 процесса на разных хостах — пересмотреть (NTP обязателен). Нельзя сравнивать время приложения с `now()` в одном предикате.
**Пр** unit-тесты фаз на границах `deadline−1мкс / ==deadline / +1мкс`; integration «голос на дедлайне» с FakeClock.

Граница: открыто, пока `now < deadline`. «За сутки» = ровно 86 400 с до дедлайна (не «то же местное время вчера» — DST не влияет). API принимает только время со смещением (наивное → 422); UI показывает в поясе браузера, письма — в `DISPLAY_TZ` с подписью пояса.

### 2.2 Транзакции и блокировки
**Р** `READ COMMITTED` + явные блокировки в едином порядке **contest → idea → vote** + ограничения БД. Время `now` читается **после** получения блокировки.

| Операция | Транзакция |
|---|---|
| Подать идею | `SELECT contest FOR SHARE` → now → проверка `now < submission_deadline` → `INSERT ... ON CONFLICT (author_id, client_request_id) DO NOTHING RETURNING` (повтор → вернуть существующую) |
| Править идею | contest `FOR SHARE` → idea `FOR UPDATE` (+ author check) → now → фаза → UPDATE |
| Удалить идею | contest `FOR SHARE` → idea `FOR UPDATE` → фаза ≠ finished → `DELETE` (голоса каскадом) → событие после commit |
| Голос | contest `FOR SHARE` → idea `FOR SHARE` (автор ≠ голосующий) → now → фаза voting → `INSERT ... ON CONFLICT DO NOTHING` |
| Отзыв голоса | contest `FOR SHARE` → now → фаза voting → `DELETE` (0 строк → тоже 204) |
| Изменить дедлайны (если будет) | contest `FOR UPDATE` (ждёт всех писателей) |
| Финализация | contest `FOR UPDATE` → now ≥ voting_deadline → `UPDATE ... WHERE finalized_at IS NULL RETURNING` → подсчёт → outbox |

**П** `FOR SHARE` на конкурсе не мешает параллельным голосам, но блокирует изменение дедлайна и финализацию до завершения начатых записей: голос, принятый в 11:59:59.99 и зафиксированный в 12:00:00.02, гарантированно попадёт в итог (финализатор ждёт его). **А** `SERIALIZABLE` — проще рассуждать, но ретраи на каждом конфликте и сложнее объяснить; хранимый флаг фазы — нужен планировщик для закрытия (П1 нарушится при его остановке). **О** Момент решения — время обработки сервером, не клика: клик в 11:59:59.9 с доставкой в 12:00:00.1 отклоняется (UI блокирует кнопки по серверному смещению и предупреждает). **Пр** integration-тесты с двумя соединениями и барьерами (`asyncio.Event`, без sleep).

Гонки:
- **Удаление идеи ‖ голос.** Удаление первым → FK-проверка вставки голоса падает (23503) → 404 «Идея удалена». Голос первым → DELETE ждёт `FOR SHARE`, затем каскадом удаляет голос. Сиротских голосов не бывает (FK).
- **Правка ‖ закрытие приёма.** Проверка `now` после блокировки в той же транзакции; «закрытие» не действие, а время → гонки нет; ответ 409.
- **Две вкладки голосуют** → PK `(idea_id, voter_id)`, второй — no-op, 200.
- **Дедлоки**: единый порядок блокировок; на `40P01`/`40001` — повтор всей транзакции до 3 раз с джиттером (безопасно: транзакция не зафиксирована). `lock_timeout=2s` → 503 вместо зависания.

### 2.3 Идемпотентность и неизвестный результат
PUT/DELETE голоса идемпотентны. Создание идеи — `client_request_id` (UUID с клиента). Обрыв соединения во время COMMIT → результат неизвестен → клиент получает 503 и безопасно повторяет (все записи идемпотентны). Финализация и напоминания — идемпотентны ключами.

### 2.4 Пулы, таймауты, недоступность БД
- SQLAlchemy async (asyncpg): `pool_size=10, max_overflow=5, pool_timeout=5s, pool_pre_ping=True, pool_recycle=1800`; + 1 выделенное соединение под singleton-lock (§5.4). Postgres `max_connections=100` — запас для тестов/psql.
- `server_settings`: `statement_timeout=5s` (запросы API), `lock_timeout=2s`, `idle_in_transaction_session_timeout=30s`, `application_name=ideas-app`.
- Старт: ожидание БД до 60 с с backoff, затем выход с понятным сообщением (код 1).
- БД недоступна в работе: readiness = 503; запросы → 503 `{"code":"service_unavailable"}` + `Retry-After`; без автоповторов записей внутри запроса (кроме §2.2); планировщик пропускает тик и логирует.

## 3. Фоновые задачи

**Р** Один asyncio-цикл в процессе приложения (`SCHEDULER_INTERVAL=15s`, первый тик сразу при старте — догоняем пропущенное), каждый тик под `pg_try_advisory_xact_lock` (не получилось → пропуск). Отправщик почты — отдельная asyncio-задача. **П** Две задачи и одна реплика — Celery/Redis не оправданы. **А** APScheduler — та же модель, лишняя зависимость; cron в контейнере — второй процесс, хуже диагностика. **О** Точность срабатывания ±интервал; это только для писем/финала — фазы от планировщика не зависят. **Пр** тесты вызывают `run_tick(now)` напрямую с FakeClock; цикл не тестируется sleep-ами.

### 3.1 Финализация
`UPDATE contests SET finalized_at=:now, winner_idea_id=:w WHERE id=:id AND finalized_at IS NULL AND voting_deadline <= :now` под `FOR UPDATE`; в той же транзакции — outbox-строки `dedup_key = final:{contest}:{user}` с `ON CONFLICT DO NOTHING`. Два процесса/тика: второй видит `finalized_at IS NOT NULL` → no-op. Результаты после дедлайна видны всем сразу по фазе (не ждут тика); `winner_idea_id` фиксирует итог для писем. После финала идеи/голоса неизменяемы (фаза finished запрещает запись).

### 3.2 Напоминания (П9)
Условие: `deadline − 24h ≤ now < deadline` и раунд ещё открыт. Одна транзакция:
`INSERT INTO reminders(contest_id, round, user_id) SELECT ... FROM users WHERE role='employee' AND is_active AND NOT EXISTS(участие) ON CONFLICT DO NOTHING RETURNING user_id` → outbox для вернувшихся, `not_after = deadline`, `dedup_key = remind:{contest}:{round}:{user}`.
Участие: подача — есть хотя бы одна (неудалённая) идея в конкурсе; голосование — есть хотя бы один голос в конкурсе. Простой приложения через весь интервал → напоминание не уходит (после дедлайна бессмысленно; `not_after` → `expired`). Конкурс создан менее чем за 24 ч до дедлайна → напоминание на ближайшем тике (открытый вопрос §11). Остаточно: человек проголосовал между тиком и доставкой — письмо всё равно придёт.

### 3.3 Outbox и доставка — честно
Цикл отправщика:
1. Транзакция: `SELECT ... WHERE status IN ('pending','sending') AND next_attempt_at <= :now AND (lease_until IS NULL OR lease_until < :now) ORDER BY id LIMIT 20 FOR UPDATE SKIP LOCKED` → `status='sending', lease_until=now+60s, attempts+=1` → commit.
2. Для каждой: если `not_after < now` → `expired`; иначе SMTP (таймаут 10 с, Message-ID детерминирован: `<{sha256(dedup_key)}@ideas.local>`).
3. Успех → `sent, sent_at`. 4xx/сеть → `pending`, `next_attempt_at = now + min(2^attempts мин, 1 ч)`; после 8 попыток или 5xx → `failed` (видно в `make status`).

**Гарантии:** создание письма — exactly-once (уникальный `dedup_key` в одной транзакции с доменным событием). Доставка — **at-least-once**: если процесс упал после ответа SMTP 250 и до commit `sent`, после истечения аренды письмо уйдёт повторно. Exactly-once поверх SMTP невозможен; окно дубля — миллисекунды между 250 и commit; детерминированный Message-ID позволяет дедуплицировать реальному MTA (Mailpit — нет). Порядок писем не гарантируется и не нужен.
Graceful shutdown: перестать брать новые, дождаться текущего письма ≤10 с, незавершённые вернутся по аренде.

## 4. Real-time: нужно ли WebSocket + LISTEN/NOTIFY

**Р** LISTEN/NOTIFY — **N/A**: при инварианте «один процесс приложения» все записи проходят через него; достаточно **внутрипроцессной шины**, публикующей события **после commit** (хук `after_commit`, иначе клиент увидит откатившуюся запись). Транспорт — один push-канал (WS или SSE — выбор за агентом API; с моей стороны SSE проще: однонаправленный, авто-reconnect, обычная cookie-авторизация). События — **сигналы инвалидации** (`idea_deleted{id}`, `ideas_changed`, `results_changed` только организатору), данные клиент перечитывает REST-ом.
**П** Минимальная архитектура; нет слушающего соединения, переподключений LISTEN, лимита 8 КБ payload.
**А** LISTEN/NOTIFY — нужен только при >1 процессе; polling 2–3 с — самый простой и надёжный, но «сразу» (П11) хуже и лишняя нагрузка.
**О** Требует `uvicorn --workers 1` — валидируется в конфиге (`WEB_CONCURRENCY` ≠ 1 → отказ старта). Изменения, внесённые мимо приложения (psql), событий не дают.
**Ресинхронизация:** события теряются при обрыве — это допустимо, потому что при каждом (пере)подключении и при `visibilitychange` клиент перечитывает состояние; дополнительно фоновый refetch раз в 30 с. Корректность (голос за удалённую идею, после дедлайна) обеспечивает сервер, а не доставка событий. Приватность: в фазе подачи сотрудникам события о чужих идеях не шлются; счётчики — только организатору.
**Пр** e2e: две вкладки, удаление идеи → исчезает во второй без перезагрузки; integration: событие публикуется только после commit (rollback → нет события).

## 5. Docker и инвариант «не более одного контейнера приложения на Docker-хост»

### 5.1 Состав и область действия
`compose.yaml`: `name: ideas-competition`; сервисы `app` (контейнер приложения, единственный), `db` (postgres:16), `mailpit`. `db`/`mailpit` — инфраструктура, не реплики приложения.
**Область гарантии:** (а) контейнеры на одном Docker-хосте — жёстко (имя контейнера); (б) любые процессы сервера, подключённые к одной БД (uvicorn локально, IDE, контейнер) — жёстко (advisory lock); (в) другие БД/хосты — вне области. Один процесс внутри контейнера (`--workers 1`).

### 5.2 Уровни защиты
| Уровень | Механизм | Что ловит | Не ловит |
|---|---|---|---|
| 1. Скрипт | `scripts/up.sh` (обёртка `make up`): хостовый lock + preflight + postcheck | одновременный `make up` из двух терминалов/клонов | прямой `docker compose` |
| 2. Docker daemon | `container_name: ideas-competition-app` — имя уникально на демоне, проверка атомарна | `compose up` с другим `-p`, `--scale app=2` (отказ), второй клон репозитория | `docker compose run` (даёт имя `...-app-run-xxx`), ручной `docker run` |
| 3. Обнаружение | label `org.ideas-competition.role=app` на сервисе (наследуется `run`) | любые контейнеры с образом/сервисом проекта | контейнеры, собранные мимо compose без label |
| 4. БД | session `pg_try_advisory_lock(0x1DEA, 1)` на выделенном соединении сервера | второй сервер против той же БД (локальный uvicorn, IDE, `compose run app`) | другую БД |

Хостовый lock: **на macOS нет `flock`** (у владельца Mac) → переносимо: атомарный `mkdir /tmp/ideas-competition.up.lock` с PID внутри; занят и PID жив → «запуск уже идёт (PID n)», exit 75; PID мёртв → снять устаревший lock. `trap 'rm -rf "$LOCK"' EXIT INT TERM`. Lock в `/tmp`, а не в репозитории — чтобы два клона тоже конфликтовали.

Advisory lock: берётся при старте (повторы до 30 с — ждём, пока старый контейнер освободит при перезапуске), иначе выход с сообщением «Другой экземпляр приложения уже подключён к этой БД (pid/addr из pg_stat_activity, application_name)». Проверка соединения каждые 10 с; потеря (рестарт БД) → попытка перезахвата; занят другим → readiness=false и завершение (exit 1). Скрипты в `exec` (pytest, alembic) lock не берут.

### 5.3 `scripts/up.sh` (предлагаемый алгоритм)
1. Проверки окружения: `docker info`, `docker compose version` ≥ 2.20, свободен порт 8000 → иначе понятная ошибка.
2. Хостовый lock (выше).
3. Preflight: `docker ps -a --filter label=org.ideas-competition.role=app --format '{{.ID}} {{.Names}} {{.Label "com.docker.compose.project"}} {{.Status}}'`. Чужой проект/имя/`-run-` → **не удалять**, вывести список и команды, которыми пользователь сам остановит; exit 1.
4. `.env` нет → скопировать `.env.example` (только dev-значения).
5. `docker compose up -d --build --wait --remove-orphans` (`--remove-orphans` трогает только наш project name).
6. Postcheck: число контейнеров с label = 1 и running → иначе exit 1 с диагностикой (`docker compose logs --tail=100 app`).

Сопутствующие (все предлагаемые): `make down` = `docker compose down` (**без `-v`**); `make destroy` — удаление volume только после ввода имени проекта; `make logs`, `make status` (контейнеры + `/health/details`), `make migrate` = `docker compose exec app alembic upgrade head`, `make shell`, `make psql` = `exec db psql`. **`docker compose run` для задач запрещён** правилом и CLAUDE.md; всё через `exec` в работающем контейнере.

### 5.4 Тесты и инвариант (решение явно)
**Р** Отдельный тестовый compose-стек (другой project name + свой app) **не используем** — это второй контейнер приложения на хосте.
- **Unit/integration (pytest)** — в CI без Docker-приложения: Postgres как service-контейнер, приложение in-process через ASGI-транспорт httpx. Локально — `make test` = `docker compose exec app pytest` против отдельной БД `ideas_test` в том же контейнере `db` (создаётся init-скриптом); планировщик и singleton-lock в тестовом процессе выключены.
- **E2E (Playwright)** — `make e2e` **переключает единственный** контейнер `app` в `APP_ENV=test` (БД `ideas_e2e`, тестовые часы), прогоняет Playwright на хосте (или `docker run --rm --name ideas-competition-e2e-$$ --label org.ideas-competition.role=tool` + trap `docker rm -f`), затем возвращает dev-конфигурацию. Dev-данные не трогаются (другая БД), но dev-приложение недоступно на время e2e — осознанно.
**А** Отдельный стек — изоляция лучше, но нарушает инвариант; testcontainers — то же нарушение для app (для БД допустимо). **О** Нельзя одновременно разрабатывать в браузере и гонять e2e. **Пр** `scripts/check_singleton.sh` после `make e2e` — 1 контейнер.

### 5.5 Сценарий проверки инварианта (`scripts/check_singleton.sh`, предлагаемый; тот же шаг в CI)
1. `make up` → контейнеров с label: 1; запомнить ID.
2. `make up` повторно → 1, тот же ID (нет изменений конфигурации).
3. `make up & make up; wait` → один ждёт/выходит с «запуск уже идёт»; итог 1.
4. Обход скрипта: `docker compose -p other up -d app` → ошибка конфликта имени; итог 1.
5. Локальный `uvicorn app.main:app` с `DATABASE_URL` на compose-БД → выход «другой экземпляр подключён».
6. Подсчёт: `docker ps -aq --filter label=org.ideas-competition.role=app | wc -l` = 1.
7. `make down` → 0 контейнеров приложения, volume `ideas-competition_pgdata` существует.

### 5.6 Перезапуск, ресурсы, тома
- Перезапуск = stop → start одного контейнера: **простой ~5–15 с** (без blue/green — второй контейнер запрещён). Правило эксплуатации: не перезапускать в последний час перед любым дедлайном (`make up` предупреждает, если `/health/details` сообщает ближайший дедлайн < 1 ч).
- `restart: unless-stopped`, `init: true` (сигналы PID 1), `stop_grace_period: 20s`, healthcheck через python urllib на `/health/ready` (curl в slim нет); `depends_on: db: condition: service_healthy`.
- Порты только `127.0.0.1:8000`, `127.0.0.1:8025` (Mailpit), БД наружу не публикуется (или `127.0.0.1:5433` в dev).
- Лимиты: app `mem_limit: 512m, cpus: 1.0, pids_limit: 256`; db `512m`. Логи `json-file` с `max-size: 10m, max-file: 3`.
- Volumes: именованный `pgdata`; ни один «обычный» сценарий не содержит `-v`/`volume prune`.

## 6. Миграции (Alembic)

**Р** Миграции применяются entrypoint-ом контейнера перед стартом uvicorn (быстрый запуск О9) под `pg_advisory_xact_lock(0x1DEA, 3)`, `lock_timeout=5s`, `transaction_per_migration=True`; вручную — `make migrate` (exec). Правила **expand/contract**: миграция либо только добавляет (таблица, nullable-колонка/с default, индекс), либо только удаляет то, что уже не используется **предыдущей** выпущенной версией приложения. Перенос данных — отдельная миграция, батчами, идемпотентно.
**Совместимость при откате приложения:** версия N обязана работать на схеме N+1 (expand). Старый образ увидит неизвестную ему ревизию в `alembic_version` → entrypoint **не мигрирует и не стартует**, сообщение «БД на ревизии X, приложению известна Y; откат схемы требует решения оператора», старт только с `ALLOW_NEWER_SCHEMA=1`. `downgrade` пишется для разработки, в эксплуатации откат схемы = восстановление из бэкапа.
**А** Отдельный migrate-контейнер/`compose run` — нарушает инвариант; ручной запуск — забывается. **О** Миграция на старте удлиняет простой; при больших данных `CREATE INDEX CONCURRENTLY` (вне транзакции, `autocommit_block`). **Пр** CI: пустая БД → `upgrade head` → `alembic check` (модели = схема) → `downgrade -1` → `upgrade head`; тест «приложение N на схеме N+1» для каждой expand-миграции при наличии предыдущего релиза.

## 7. Бэкап, восстановление, хранение

- `make backup` → `docker compose exec -T db pg_dump -Fc -U $USER ideas > backups/ideas-<UTCts>.dump` + манифест (ревизия alembic, число строк по таблицам). `backups/` в `.gitignore`, права 600 (в дампе ПДн и авторство).
- `make restore-check FILE=…` — без нового контейнера: в том же `db` создать `ideas_restorecheck`, `pg_restore --exit-on-error --no-owner`, сравнить с манифестом, удалить БД. Восстановление не считается рабочим, пока это не пройдено (шаг CI на тестовых данных).
- `make restore FILE=…` — `docker compose stop app` → пересоздать БД → `pg_restore` → `make up`. Подтверждение вводом имени.
- Хранение: просроченные сессии — удаляются ежедневно тиком; `outbox.body` → NULL через 30 дней после `sent/failed/expired` (метаданные остаются для аудита); идея удаляется физически (так требует ТЗ); пользователей не удаляем — деактивация (`is_active=false`), при запросе на удаление — обезличивание (имя/e-mail → заглушка), т.к. FK RESTRICT на идеях/голосах. Бэкапы локально: хранить 7 последних (prod-план: 30 дней).

## 8. Конфигурация и жизненный цикл

**Версии (pin):** Python 3.12 (`python:3.12-slim-bookworm`; локально через `uv python install 3.12` — системный 3.9 на Mac не годится), `uv` + `uv.lock`; Node 22 LTS + `package-lock.json`, `npm ci`; `postgres:16.x-alpine`; `axllent/mailpit:v1.x` (точный тег при реализации); Docker Compose ≥ 2.20. Файл `.tool-versions`/`.python-version` + проверка в `up.sh`.

**pydantic-settings** (`APP_ENV`: dev|test|prod), ошибка → список всех проблем **без значений секретов**, exit 2:
| Переменная | Обяз. | Правило |
|---|---|---|
| `DATABASE_URL` | да | `postgresql+asyncpg://` |
| `ORGANIZER_LOGIN/EMAIL/PASSWORD` | да | prod: длина ≥ 12 и ≠ значению из `.env.example` |
| `SMTP_HOST/PORT`, `MAIL_FROM` | да | |
| `PUBLIC_BASE_URL` | да | prod: https |
| `DISPLAY_TZ` | нет (`Europe/Moscow`?) | валидный IANA |
| `SCHEDULER_INTERVAL_S` | нет (15) | 5–300 |
| `WEB_CONCURRENCY` | нет (1) | только 1 |
| `TEST_CLOCK_ENABLED` | нет | true разрешено только при `APP_ENV=test` |
| `LOG_LEVEL`, `LOG_FORMAT` | нет | json в контейнере |

`.env.example` — только заглушки, помечен «dev only». Первый запуск: миграции → сид организатора (идемпотентно, `ON CONFLICT DO NOTHING`) → демо-данные только при `SEED_DEMO=true` в dev.

**Health:** `/health/live` (процесс жив, без БД) — для отладки; `/health/ready` (БД `SELECT 1` ≤1 с, singleton-lock удержан, схема совместима) — healthcheck Docker; `/health/details` (только организатор/локально): лаг планировщика, outbox pending/failed/возраст старейшего, пул, ближайший дедлайн.

**Graceful shutdown (SIGTERM):** readiness=false → uvicorn перестаёт принимать, `timeout_graceful_shutdown=10s` для активных запросов → остановить планировщик между тиками (тик ≤5 с) → отправщик заканчивает текущее письмо → закрыть push-соединения (WS 1012 / SSE close — клиенты переподключатся и ресинхронизируются) → закрыть singleton-соединение (lock снимается) → `engine.dispose()`.

**Диагностика запуска** (README-таблица): порт занят; Docker не запущен; конфликт имени контейнера (выводим чей); lock занят; БД не готова за 60 с; неверная конфигурация (список полей); неизвестная ревизия схемы; advisory lock занят другим процессом (адрес из `pg_stat_activity`).

## 9. Наблюдаемость и CI

**Логи:** JSON в stdout (structlog): `ts, level, event, request_id, user_id, contest_id, route, status, duration_ms`; фоновые — `job, run_id, outbox_id`. Correlation: `X-Request-ID` принимается, если `^[A-Za-z0-9-]{1,64}$`, иначе генерируется; возвращается в ответе и в теле ошибки. Никогда не логируются пароли, токены, cookie, тела писем; e-mail маскируется (`a***@d.com`); связка автор↔идея в логах фазы голосования не пишется.
**Метрики:** Prometheus — **N/A**: нет сервера сбора в минимальном стеке, эндпоинт без сборщика ничего не доказывает. Вместо — `duration_ms` в логах и `/health/details` (§8). Оповещения — N/A локально; оператор смотрит `make status`: `failed` в outbox > 0, лаг планировщика > 2 мин, readiness ≠ 200.

**CI (GitHub Actions, предлагаемый):** 1) backend: `ruff format --check`, `ruff check`, `mypy --strict`; 2) frontend: `prettier --check`, `eslint`, `tsc --noEmit`, `vite build`; 3) pytest (unit + integration, service `postgres:16`), миграции (§6), grep-проверка `now()`; 4) `pip-audit`, `npm audit --audit-level=high`; 5) `docker build` + `make up` + `scripts/check_singleton.sh` + smoke (`/health/ready`, логин организатора, `GET /api/contests`) + `make backup && make restore-check` + `make e2e` + `make down`; при падении — артефакт `docker compose logs`. Runner — отдельный Docker-хост с одним app-контейнером: инвариант соблюдён.

**Выкладка (план prod, не реализуется):** бэкап → образ с тегом git sha → stop app → миграции (только expand) → start → smoke → при неудаче вернуть предыдущий образ (схема совместима) → при порче данных — restore. Не выкладывать в последний час перед дедлайном.

## 10. Матрица пограничных случаев (зона Data & Ops)

| Сценарий | Ожидаемое поведение | Механизм | Тест | Остаточный риск |
|---|---|---|---|---|
| Пустой/пробельный title, >200/10 000 симв. | 422 | Pydantic + CHECK | unit+int | — |
| Emoji/комбинирующие символы, NUL-байт | хранится как есть; `\x00` → 422 | валидация, UTF8 БД | int | длина считается в code points |
| Время без смещения / voting ≤ submission | 422 | Pydantic + CHECK | unit+int | — |
| Голос/правка ровно в `deadline` | 409 | `now < deadline` после блокировки | int (FakeClock) | задержка сети на стороне клиента |
| Голос на дедлайне ‖ финализация | голос либо в итоге, либо 409 | `FOR SHARE` vs `FOR UPDATE` | int, 2 соединения | — |
| Удаление идеи ‖ голос за неё | нет сиротских голосов; голос → 404 | FK + CASCADE | int, 2 соединения | — |
| Два голоса из двух вкладок | один голос | PK `(idea_id,voter_id)` | int + e2e | — |
| Повтор POST идеи после таймаута | одна идея | `UNIQUE(author_id, client_request_id)` | int | старый клиент без ключа |
| Дедлок/serialization failure | прозрачный повтор ≤3 | порядок блокировок + retry | int | 503 после 3 |
| Финализация двумя процессами/тиками | одна запись, письма по одному | условный UPDATE + dedup_key | int | — |
| Падение между SMTP 250 и commit | письмо повторно | аренда + at-least-once | int (фейковый SMTP) | дубль письма (честно) |
| SMTP недоступен/медленный | backoff, `failed` после 8 | таймаут 10 с, статусы | int | задержка писем |
| Приложение лежало весь интервал напоминаний | не шлём после дедлайна | `not_after` → expired | int | напоминание потеряно |
| Напоминание ‖ участие в ту же секунду | максимум одно, возможно лишнее | PK reminders | int | лишнее письмо |
| БД недоступна / медленная | 503 + Retry-After, ready=503 | таймауты пула/statement | int (остановка db) | — |
| Пул исчерпан | 503 через 5 с | `pool_timeout` | int | — |
| SIGTERM во время запроса/тика/письма | запрос завершается ≤10 с, тик откатывается, письмо по аренде | lifespan shutdown | int/ручной | — |
| SIGKILL / OOM | транзакции откатываются, задачи догоняются на старте | атомарность БД, первый тик | ручной | простой |
| Повторный `make up` | no-op, тот же контейнер | compose idempotent | check_singleton | — |
| Конкурентный `make up` / `-p other` / `--scale` | 1 контейнер | mkdir-lock, container_name | check_singleton | — |
| `docker compose run app …` | обнаруживается, сервер не стартует | label + advisory lock | check_singleton | контейнер существует до ручной остановки |
| Локальный uvicorn при работающем контейнере | отказ старта | advisory lock | check_singleton | другая БД — вне гарантии |
| Рестарт БД при работающем app | lock перезахвачен или app выходит | проверка соединения 10 с | ручной | окно ≤10 с |
| Нет места на диске | запись → 503, логи ограничены | log rotation | ручной | БД read-only до очистки |
| Миграция упала | контейнер не стартует, схема в последней успешной ревизии | `transaction_per_migration` | CI | частичная серия миграций |
| Откат приложения на старую версию | отказ старта с объяснением | проверка ревизии | CI | ручное решение оператора |
| Бэкап не восстанавливается | обнаруживается до нужды | restore-check в CI | CI | разные версии pg_dump |
| Конкурс создан < 24 ч до дедлайна | напоминание на ближайшем тике | условие окна | int | см. вопрос 3 |
| Смена DST между созданием и дедлайном | мгновение не сдвигается | timestamptz | unit | неверный ввод пояса организатором |

## 11. Риски и открытые вопросы

**Риски:**
1. Инвариант не абсолютен: ручной `docker run` без label с другой БД не обнаруживается — граница гарантии задокументирована.
2. Простой при каждом перезапуске (нет blue/green по определению) — отклонённые голоса, если рестарт у дедлайна.
3. Дубли писем возможны (at-least-once) — честно в README.
4. e2e занимает единственный app-контейнер — dev-приложение недоступно на время прогона.
5. Последовательные id идей раскрывают порядок подачи (не автора); при требовании строгой анонимности — UUID наружу.
6. Docker Desktop на Mac владельца не проверен (facts.md); `flock` на macOS отсутствует — учтено mkdir-lock.

**Вопросы владельцу/другим агентам:**
1. Подтвердить допущение 1 (SPA внутри app-контейнера) — от него зависит инвариант.
2. Может ли организатор менять дедлайны после создания? Если нет — блокировку `FOR UPDATE` для правки дедлайнов не реализуем.
3. Конкурс создан менее чем за 24 ч до закрытия раунда: слать напоминание сразу или не слать?
4. «Участвовал в раунде подачи», если подал и удалил идею — считать участником? (предложение: нет).
5. Транспорт push — WS или SSE (агент API); с моей стороны LISTEN/NOTIFY не нужен в любом случае.
6. `DISPLAY_TZ` по умолчанию — какой пояс компании?
7. Приемлем ли отказ от отдельного тестового стека (e2e переключает единственный контейнер)?
