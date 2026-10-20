# CLAUDE.md — «Конкурс идей»

Главный документ проекта для разработчиков и AI-агентов. Здесь записаны требования ТЗ, архитектура,
обязательные правила и журнал решений. Подробные обоснования, матрица пограничных случаев и runbook
вынесены в `docs/` (ссылки ниже). Ключевые решения и обязательные правила остаются здесь.

> **Статус: архитектура и план разработки утверждены владельцем 2026-10-20 06:09; срок сдачи — суббота 2026-10-24. Сделаны структура пакетов backend и доменные модели; дальше — задачи `Documents/Конкурс идей/TODO.md`.**
> Всё, что описано ниже как структура, команды и механизмы, — **предлагаемое состояние**, кроме явно помеченного «(проверено)».
> Проверено на сегодня только для `backend/`: `uv run pytest -m unit`, `ruff`, `mypy --strict`, `lint-imports`, `pip-audit` (§2.1, §6.1; в GitHub Actions — со смержа IC-002). Остальные команды помечены «(план)».
> Каждый следующий этап начинается только по указанию владельца проекта (Ilia).

## 0. Как пользоваться документом

| Нужно | Раздел |
|---|---|
| Понять, что требует ТЗ | §1 |
| Понять, что есть сейчас и что будет | §2 |
| Куда положить новый код, какие зависимости можно | §4, §5 |
| Как именовать и обрабатывать ошибки | §6 |
| Как работать с БД, транзакциями, временем | §7 |
| Контракт API и фоновые задачи | §8 |
| Вход, права, безопасность | §9 |
| Какие тесты обязательны | §10 |
| Как запустить, остановить, проверить один экземпляр | §11, §12, `docs/runbook.md` |
| Наблюдаемость, CI, восстановление | §13 |
| Пограничные случаи | `docs/edge-cases.md` |
| Почему решения именно такие (три прохода анализа) | `docs/architecture-review.md` |
| Как проверить свой код перед коммитом (самопроверка Senior) | §6.5 |
| Когда изменение готово | §14 (Definition of Done) |
| План разработки, задачи IC-NNN и их статусы | `Documents/Конкурс идей/TODO.md` |
| Как вести отчёт для сдачи | §15–§18 |

Правило приоритета: **ТЗ → этот документ → `docs/*` → код**. Если код расходится с документом,
это дефект одного из них; исправлять в том же изменении.

---

## 1. Требования ТЗ (чек-лист трассировки)

Источник: `ТЗ.docx`, «Требования» и «Задание 7. Конкурс идей». Номера используются в тестах и журнале.

### Общие требования

| №  | Требование ТЗ | Как закрываем | Статус |
|----|---------------|---------------|--------|
| О1 | Клиент-сервер: отдельный backend и frontend, общаются по сети | `backend/` и `frontend/` — отдельный код, сборка и тесты; браузер общается с backend только по HTTP и WebSocket. SPA отдаётся тем же контейнером (§3, решение Р1) | спроектировано |
| О2 | Backend: Python/Go/Node, обосновать выбор | Python 3.12 + FastAPI (§5) | спроектировано |
| О3 | Frontend: Vue или React | React 18 + TypeScript + Vite | спроектировано |
| О4 | Реляционная СУБД, предпочтительно PostgreSQL | PostgreSQL 16 | спроектировано |
| О5 | Учётные записи — на усмотрение | E-mail + пароль, роли «сотрудник» и «организатор» (§9) | спроектировано |
| О6 | Лог решений / промпты вместе с кодом | §17, `docs/prompts.md`, `docs/architecture-review/` | ведётся |
| О7 | Использование AI-агентов не скрывается | §15 | ведётся |
| О8 | Описаны предварительные требования к развёртыванию | §11.1, `README.md` | спроектировано |
| О9 | Быстрый локальный запуск | `make up` (план) | спроектировано |
| О10 | Внешние сервисы можно эмулировать | Почта → Mailpit | спроектировано |
| О11 | Работает при двух открытых клиентах | Состояние на сервере, push по WebSocket, e2e с двумя браузерами | спроектировано |
| О12 | Честное описание состояния | `README.md` → «Состояние проекта» | ведётся |
| О13 | Доказуемость работоспособности | Тесты §10, сценарий проверки инварианта §12.4, CI §13 | спроектировано |

### Что сдаём (раздел ТЗ «Что мы ожидаем от вас»)

| №  | Ожидание ТЗ | Где лежит | Как обеспечивается | Статус |
|----|-------------|-----------|--------------------|--------|
| С1 | Ссылка на GitHub | `README.md` → «Репозиторий» | Локальный git с первого шага; remote подключается после создания репозитория владельцем | ждёт репозиторий |
| С2 | Модель, инструмент, почему | `README.md`, §15 | — | готово |
| С3 | Промпты / лог решений / экспорт сессии | `docs/prompts.md`, §17, `docs/architecture-review/`, экспорт jsonl | Правила §16 | ведётся; экспорт ждёт согласия владельца |
| С4 | Ход работы во времени | История git, метки UTC в §17 и `docs/prompts.md`, §18 | Коммит на этап, история не переписывается | ведётся |
| С5 | Как развернуть и состояние | `README.md` | Обновляется в конце каждого этапа | каркас |
| С6 | Что сделали бы следующим заходом | `README.md` | Пополняется по ходу | ведётся |
| С7 | Чужие решения, шаблоны, генераторы | `README.md`, §15 | Запись в момент использования | ведётся |

### Функциональные требования

| №  | Требование ТЗ | Как закрываем |
|----|---------------|---------------|
| Ф1 | Конкурс: тема, закрытие приёма идей, закрытие голосования | `contests.topic`, `submission_deadline`, `voting_deadline` (timestamptz), `CHECK submission_deadline < voting_deadline`; дедлайны неизменяемы после создания (Р13) |
| Ф2 | Подача: название и описание, правка до закрытия | `POST /api/contests/{id}/ideas`, `PATCH /api/ideas/{id}` с проверкой фазы и `version` |
| Ф3 | Голосование: идеи без авторов, один голос на идею от человека | Схема `IdeaForVoting` без полей автора; PK `votes(idea_id, voter_id)` |
| Ф4 | Финал: результаты, авторы раскрываются, письмо победителю и всем участникам | Фаза `finished`; финализация на тике; outbox → Mailpit; победителю «Вы победили», авторам остальных идей «Ваша идея не прошла» |
| Ф5 | Экран организатора: число идей, число проголосовавших, текущие результаты | `GET /api/organizer/contests/{id}/dashboard` + сигналы WebSocket |

### Ожидаемое поведение

| №  | Требование ТЗ | Как закрываем | Чем доказываем |
|----|---------------|---------------|----------------|
| П1 | Раунды закрываются сами по времени | Фаза вычисляется из `Clock` и дедлайнов, флага «закрыт» нет | unit `ContestSchedule.phase_at` на границах; int финализации |
| П2 | Идея и голос после закрытия не принимаются, даже если страница открыта | Проверка фазы на сервере в транзакции после блокировки конкурса; `now` читается после блокировки | int с FrozenClock; e2e «форма открыта → время сдвинуто → отправка → 409» |
| П3 | Во время подачи чужие идеи не видны | API отдаёт только свои; события WS о чужих идеях не отправляются | int, contract |
| П4 | В голосовании все идеи без авторов; за свою нельзя | `IdeaForVoting` без автора и времени; UUID-идентификаторы; 403 `own_idea_vote` | contract (точный набор ключей), int, e2e |
| П5 | Один голос на идею при любом числе вкладок | PK в БД + `ON CONFLICT DO NOTHING` | int (параллельные запросы), e2e (две вкладки) |
| П6 | Голос можно отозвать до закрытия | `DELETE /api/ideas/{id}/vote` с проверкой фазы, идемпотентно | int |
| П7 | Организатор видит изменения без обновления страницы | Сигнал `results_changed` только организатору → refetch | e2e (голос в контексте A → цифра у организатора) |
| П8 | Остальные видят результаты только после финала | `can_view_results`: организатор или фаза `finished` | int на `deadline − 1µs` и `deadline` |
| П9 | За сутки до закрытия раунда — одно напоминание не участвовавшим | Тик планировщика; PK `reminders(contest_id, round, user_id)` в одной транзакции с outbox | int (два тика, параллельно) |
| П10 | Ничья → раньше поданная; правило видно заранее | `rank_ideas`: голоса ↓, `submitted_at` ↑, `id` ↑; текст правила на странице конкурса с фазы подачи | unit (property-based), e2e |
| П11 | Удалённая во время голосования идея исчезает у всех сразу вместе с голосами | `ON DELETE CASCADE`; сигнал `idea_deleted` всем после commit | int, e2e (удаление в A → исчезает в B ≤ 2 с) |

**Толкования неоднозначностей ТЗ** (приняты, видны пользователю в README):
- «Сразу», «без обновления страницы» — не дольше 2 с в e2e.
- «Не участвовал» — по текущему состоянию: нет текущих идей в конкурсе (раунд подачи) / нет текущих голосов в конкурсе (раунд голосования). Отозвавший все голоса или потерявший голос из-за удалённой идеи получит напоминание.
- «Все участники» финального письма — авторы текущих идей и проголосовавшие. Победителю — «Вы победили», авторам остальных идей — «Ваша идея не прошла» (владелец, 06:09), тем, кто только голосовал, — итоги конкурса (06:11).
- «За сутки» — ровно 86 400 с до дедлайна. Если конкурс создан позже, напоминание уходит на ближайшем тике, пока раунд открыт.
- У всех идей 0 голосов — побеждает самая ранняя по правилу ничьей. Идей нет — победителя нет.
- Организатор до финала видит результаты **без авторов** (ТЗ не требует авторов на экране организатора; минимум привилегий).

---

## 2. Состояние: фактическое → предлагаемое → переход

### 2.1 Фактическое (проверено 2026-10-20 04:25–04:45 UTC)
- Папка `/Users/admin/PycharmProjects/IdeasCompetition` на Mac владельца.
- Есть: `CLAUDE.md`, `README.md`, `docs/`, `tools/export_agent_session.py`, `.gitignore`; шаблонный `main.py` от PyCharm (вне git); `.venv` с системным Python 3.9.6 (не подходит, нужен 3.12); `.idea/` (вне git).
- Нет: исходников, тестов, зависимостей, lock-файлов, Docker, миграций, CI, AGENTS.md.
- git: коммиты только с документацией; remote не настроен.

Обновлено 2026-10-20 05:45 UTC:
- `backend/app/` — пакеты 9 модулей по §4 со слоями `model/service/exception/controller/dao/handler`; написаны только `model` и `exception` (доменные модели), остальные слои — пустые пакеты с описанием назначения.
- `backend/tests/unit/` — 47 unit-тестов моделей; `backend/pyproject.toml` — pytest, ruff, mypy (зависимости рантайма — на этапе каркаса).
- Проверено в облачном контейнере агента (Python 3.13, `target-version`/`python_version` = 3.12): `python3 -m pytest` — 47 passed; `ruff check .`, `ruff format --check .` — без замечаний; `mypy app tests` (strict) — без ошибок. На Mac владельца не запускалось: там нет Python 3.12 и `uv` (проверка — этап каркаса).
- git: GitHub `https://github.com/JustExpo/IdeasCompetition`, ветка `main`.
- Не проверено: наличие Docker Desktop, `uv`, Node.js на Mac владельца.

### 2.2 Предлагаемое
Описано в §3–§14: модульный монолит на FastAPI в одном контейнере `app`, PostgreSQL и Mailpit
отдельными контейнерами, SPA на React внутри того же образа.

### 2.3 Переход (этапы)
Каждый этап — отдельный коммит и согласование.

1. ✓ План и требования к отчёту.
2. ✓ Архитектура и правила разработки (этот документ), утверждено владельцем 06:09.
4а. ✓ (по указанию владельца раньше каркаса) Структура пакетов backend по модулям и доменные модели с unit-тестами. ← сейчас
3. Каркас: `compose.yaml`, Dockerfile, `Makefile`, `scripts/`, пустой FastAPI с `/api/health`, Alembic, CI-заготовка, singleton-проверки. Удалить `main.py`.
4. Домен: политики доступа (`<модуль>/model/policy.py`), выбор получателей напоминаний — с unit-тестами (фазы, ранжирование, окно напоминания уже есть с этапа 4а).
5. Пользователи и вход: регистрация, сессии, роли, rate limit, CLI.
6. Конкурсы, идеи, голоса: сервисы, БД, API, integration-тесты.
7. Реальное время: шина, WebSocket-хаб, экран организатора.
8. Фоновые задачи: финал, напоминания, outbox, Mailpit.
9. Frontend: все экраны, генерация типов из OpenAPI.
10. E2E на два браузера, бэкап/восстановление, README, финальная сверка с ТЗ.

---

## 3. Архитектура

### 3.1 Принцип
Минимальная архитектура, достаточная для ТЗ: **один процесс приложения** (модульный монолит),
**инварианты держит БД**, **фаза вычисляется из времени**, **побочные эффекты — через outbox**.
Микросервисы, очереди, кэш, Redis, Celery, CQRS, event sourcing — **не используются**: нет требования,
которое они закрывают (обоснование — `docs/architecture-review.md`, раздел «Отклонённые варианты»).

### 3.2 Компоненты и потоки

```
 Браузер (вкладки A, B, организатор)       Контейнер app (1 процесс uvicorn, workers=1)
 ┌──────────────────────────┐  HTTP /api  ┌───────────────────────────────────────────────┐
 │ SPA React + TanStack     │ ──────────▶ │ controller ──▶ service ──▶ dao ──▶ model      │
 │ Query                    │ ◀────────── │            │                                   │
 │ api/events.ts (WS)       │ ◀── WS ──── │ realtime (хаб ◀ шина) ◀── service (после commit)
 └──────────────────────────┘  сигналы    │            │ db (пул asyncpg) ────────────────┼──▶ db: PostgreSQL 16
        ▲ GET / → index.html             │ core.scheduler (тик 15 с) ──▶ <модуль>.handler │
        └── статика SPA из того же образа │ notification.handler ──▶ SMTP ────────────────┼──▶ mailpit (SMTP + веб :8025)
                                          └───────────────────────────────────────────────┘
```

Основные потоки (подробно — `docs/architecture-review.md`):
1. **Запись (идея, правка, голос, удаление):** api → сервис открывает транзакцию → `SELECT contest FOR SHARE` → (`SELECT idea FOR UPDATE/SHARE`) → `now = clock.now()` → доменная политика → SQL → commit → событие в шину → хаб рассылает сигналы по правам.
2. **Чтение:** api → сервис → запрос → схема ответа, выбранная по фазе и роли (анонимность закреплена типом схемы).
3. **Финал, напоминания, письма:** планировщик раз в 15 с (и сразу при старте) вызывает сервисы; письма ставятся в outbox в той же транзакции; отправщик доставляет их отдельно.
4. **Смена фазы:** никто ничего не переключает; клиент сам перечитывает данные в момент дедлайна по серверному времени, сервер в любом случае отклонит запоздавшую запись.

### 3.3 Ключевые решения
Формат: **решение → причина → альтернативы → ограничения → проверка**. Полная версия с контрпримерами — `docs/architecture-review.md`.

| # | Решение | Причина | Альтернативы | Ограничения | Проверка |
|---|---|---|---|---|---|
| Р1 | Один контейнер `app`: FastAPI отдаёт API и собранный SPA; frontend — отдельный код и сборка | Инвариант «один контейнер приложения» (§12) + О1; один origin убирает CORS и упрощает CSRF | Отдельный nginx-контейнер frontend — нарушает инвариант | Проверяющий может счесть frontend «не отдельным» — README объясняет | Сборка образа; e2e через порт app |
| Р2 | Модульный монолит; с 05:35 по указанию владельца — модули по частям логики, в каждом слои `controller/handler → service → dao → model → exception` (§4.2); исходный вариант `api/jobs/cli → services → adapters → domain` заменён | Правила ТЗ тестируются без БД и сети; транспорт и хранилище не протекают в правила | Плоская структура; hexagonal с портами на каждый репозиторий | Интерфейсы (Protocol) только для `Clock`, `EmailSender`, `EventPublisher` | `lint-imports` в CI |
| Р3 | Фаза вычисляется из времени, `now < deadline` — раунд открыт | Закрытию «нечему не сработать» (П1) | Хранимый флаг + планировщик | Точность писем ± тик | unit на границах |
| Р4 | Время — часы приложения `Clock`, читаются после блокировки и заново при повторе транзакции | Тестируемость; `now()` PostgreSQL — время начала транзакции | `now()`/`clock_timestamp()` БД | Один процесс — одни часы | int с FrozenClock; ruff `banned-api` |
| Р5 | Инварианты в БД: PK голосов, FK + CASCADE, CHECK, уникальные ключи outbox/напоминаний | Код имеет гонки, ограничение БД — нет | Проверки в коде | — | int на каждое ограничение |
| Р6 | `READ COMMITTED` + блокировки в порядке contest → idea → vote; записи `FOR SHARE` конкурса, финализация `FOR UPDATE` | Голос, принятый до дедлайна, гарантированно попадает в итог; голоса не сериализуются между собой | `SERIALIZABLE` с ретраями | Повтор при дедлоке ≤ 3 раз | int с двумя соединениями |
| Р7 | `ideas.id` — UUIDv4, остальные PK — bigint | Последовательный id раскрывает порядок подачи и выдаёт автора | bigint везде; HMAC-порядок | — | contract, int |
| Р8 | Реальное время: WebSocket + внутрипроцессная шина; по WS только сигналы «перечитай», без данных | Один процесс → LISTEN/NOTIFY не нужен; права и анонимность проверяются в одном месте (REST) | LISTEN/NOTIFY; SSE (лимит 6 соединений HTTP/1.1 ломает «много вкладок»); polling | Событие теряется при обрыве → refetch при переподключении; `workers=1` обязателен | int «событие только после commit»; e2e |
| Р9 | Outbox: письмо создаётся exactly-once в транзакции события, доставка at-least-once | Письмо не теряется и не создаётся дважды; честная семантика SMTP | Отправка из запроса | Возможен дубль при падении между SMTP 250 и commit | int с FakeMailSender |
| Р10 | Вход по e-mail + паролю, серверные сессии в БД, cookie `HttpOnly` | Отзыв сессий; нет токенов в JS | JWT в localStorage; magic link; SSO (план прода) | Без подтверждения e-mail (Р11) | int |
| Р11 | Подтверждение e-mail и сброс пароля по почте — не в объёме; allow-list домена; сброс через CLI | Вся почта уходит в общий Mailpit: подтверждение ничего не доказывает | Подтверждение через Mailpit | Риск лишних аккаунтов (Sybil) — записан | — |
| Р12 | Один контейнер приложения: `container_name` + session advisory lock в БД + подсчёт по label | Атомарный отказ демона + защита от запуска мимо Docker | Хостовый lock-файл; только `project name` | Ручной `docker run` против другой БД — вне гарантии | `scripts/check_singleton.sh` (§12.4) |
| Р13 | Дедлайны неизменяемы после создания | Правка ломает «одно напоминание» и открытые вкладки | Правка с `FOR UPDATE` | Ошибку дедлайна чинят новым конкурсом | int (нет эндпоинта) |
| Р14 | Тесты без отдельного тестового стека: pytest на хосте против БД `ideas_test` в том же `db`; e2e переключает единственный `app` в режим e2e с БД `ideas_e2e`. Отклонение (IC-001): агент без Docker гоняет integration-тесты на локальном PostgreSQL 16 своего контейнера, Docker-часть проверяет CI | Отдельный стек = второй контейнер приложения | testcontainers, `-p ideas-e2e` | Во время e2e dev-приложение недоступно | `check_singleton.sh` после e2e |

---

## 4. Структура проекта и размещение кода

### 4.1 Дерево (план)

```
IdeasCompetition/
├── CLAUDE.md               ← этот документ
├── README.md               ← запуск, состояние, следующим заходом
├── Makefile                ← единая точка команд (§11)
├── compose.yaml            ← name: ideas-competition; сервисы app, db, mailpit
├── compose.e2e.yaml        ← override для e2e (тот же container_name)
├── Dockerfile              ← multi-stage: node собирает SPA → python runtime
├── .env.example            ← только dev-заглушки
├── scripts/                ← up.sh, check_singleton.sh, backup.sh, restore_check.sh
├── docs/
│   ├── prompts.md          ← промпты владельца дословно
│   ├── architecture-review.md  ← три прохода анализа, решения и компромиссы
│   ├── architecture-review/raw/ ← исходные отчёты агентов по раундам
│   ├── edge-cases.md       ← матрица пограничных случаев
│   ├── runbook.md          ← эксплуатация, диагностика, восстановление
│   └── agent-session/      ← экспорт сессии (вне git)
├── tools/export_agent_session.py
├── backend/
│   ├── pyproject.toml  uv.lock  .python-version  alembic.ini  .importlinter
│   ├── migrations/         ← Alembic (env.py, versions/)
│   ├── app/
│   │   ├── main.py         ← create_app(settings): сборка модулей, lifespan, SPA (этап каркаса)
│   │   ├── cli.py          ← create-organizer, reset-password, revoke-sessions, status, export-openapi
│   │   ├── core/           ← инфраструктура без бизнес-логики: config, clock, logging, db (engine,
│   │   │                     run_in_transaction), http_errors (AppError → problem+json), scheduler (цикл тиков)
│   │   ├── common/         ← общее для всех модулей: model/ (идентификаторы, время, текст), exception/ (AppError)
│   │   ├── user/           ← пользователь и роль, регистрация
│   │   ├── auth/           ← вход, сессии, действующее лицо запроса (Actor), rate limit
│   │   ├── contest/        ← конкурс, расписание, фаза
│   │   ├── idea/           ← подача, правка, удаление идеи, лимиты, идемпотентность
│   │   ├── vote/           ← голос и его отзыв
│   │   ├── result/         ← подсчёт, ранжирование, правило ничьей, финализация
│   │   ├── reminder/       ← напоминания за сутки до закрытия раунда
│   │   ├── notification/   ← outbox писем, шаблоны, отправка SMTP
│   │   └── realtime/       ← события «перечитай», шина, WebSocket-хаб
│   │       (в каждом модуле: model/ service/ exception/ controller/ dao/ handler/ — §4.2)
│   └── tests/              ← unit/, integration/, api/, contract/, fakes.py, conftest.py
├── frontend/
│   ├── package.json  package-lock.json  .nvmrc  vite.config.ts  tsconfig.json
│   ├── eslint.config.js  .prettierrc  .dependency-cruiser.cjs  openapi.json
│   └── src/  app/ api/ features/ pages/ shared/ test/
└── e2e/                    ← Playwright: package.json, playwright.config.ts, tests/
```

### 4.2 Модули, слои и направление зависимостей (backend)

Решение владельца (2026-10-20 05:29): backend делится на **модули по частям логики** (пакет на модуль),
внутри каждого модуля — одинаковые слои. Модуль называется по сущности, которой он владеет, поэтому
по пути видно, к чему относится модель: `app/idea/model/idea.py` — идея, `app/vote/model/vote.py` — голос.

| Слой | Что лежит | Что можно импортировать | Запрещено |
|---|---|---|---|
| `model` | Доменные модели (frozen dataclass), перечисления, константы-лимиты, чистые правила (`phase_at`, `rank_ideas`, `policy.py`) | `common.model`, `common.exception`, своё `exception`, `model` других модулей | I/O, `sqlalchemy`, `fastapi`, `starlette`, `pydantic`, `asyncpg`, `app.core`; чтение часов — время приходит аргументом `now` |
| `exception` | Исключения модуля: наследники `AppError` с `code` (lower_snake_case) и HTTP `status` | `common.exception` | всё остальное |
| `dao` | Таблицы SQLAlchemy и запросы модуля; перевод `IntegrityError` в исключения модуля по имени constraint | свои `model`, `exception`; `core.db` | `fastapi`; `dao` других модулей; `commit()` |
| `service` | Сценарии: транзакция через `core.db.run_in_transaction`, блокировки, проверка прав, постановка писем, публикация событий после commit | свои `model`, `exception`, `dao`; `model`, `exception`, `service` других модулей; `core` | `fastapi`, `starlette`; `dao`/`controller`/`handler` других модулей |
| `controller` | HTTP- и WebSocket-маршруты FastAPI и схемы запросов/ответов (Pydantic) | свои `service`, `model`, `exception`; `auth.service` (действующее лицо); `core` | `dao` (свой и чужой); SQL; бизнес-правила |
| `handler` | Реакции на события, не являющиеся HTTP-запросом: тики планировщика и события шины модуля; особые случаи перевода исключений модуля в HTTP (общий перевод `AppError` → problem+json один, в `core.http_errors`) | свои `service`, `exception`; `core` | `dao`; бизнес-правила |

Направление внутри модуля: `controller | handler → service → dao → model → exception`. Нижний слой
никогда не импортирует верхний.

Направление между модулями (без циклов):

```
common  ←  user  ←  auth
           user, contest  ←  idea  ←  vote  ←  result
           contest, idea, vote  ←  reminder
           notification, realtime  ← вызываются сервисами других модулей и сами их не импортируют
core    ←  все модули (только service, dao, controller, handler); core не импортирует модули, кроме main.py
```

Уточнения графа (IC-001, 2026-10-20; смержены владельцем в MR #3):
- **Список идей конкурса** (`GET /api/contests/{id}/ideas`) во всех фазах отдаёт
  `vote.service.list_contest_ideas`: идеи берёт у `idea.service`, а в фазе голосования добавляет
  `my_vote`. Поэтому маршрут живёт в `vote.controller`. Ребра `idea → vote` нет; без этого правила
  `idea` пришлось бы читать чужие голоса.
- **Напоминания** (`reminder`) читают участие через `idea.service` и `vote.service`
  (рёбра `reminder → idea`, `reminder → vote`); выбор получателей — чистая функция в `reminder.model`.
- **События реального времени:** аудиторию события вычисляет публикующий сервис по политике своего
  модуля (`idea/model/policy.py`, `vote/model/policy.py`, `result/model/policy.py`) и передаёт в
  `realtime.service` готовый список адресатов (пользователи и/или роль). `realtime` только рассылает:
  не знает фаз, авторов и идей, импортирует только `common` и `core`.
- **Итоговые письма и напоминания** ставят `result.service` и `reminder.service` через
  `notification.service`; `notification` получает готовые адрес, тему и текст.

Обязательные правила (проверяет `uv run lint-imports`, конфиг `backend/.importlinter` — 17 контрактов, проверено в IC-002 и IC-003):
- `layers` для каждого модуля: `controller | handler` > `service` > `dao` > `model` > `exception`.
- `forbidden`: `app.*.model` и `app.*.exception` не импортируют `sqlalchemy`, `fastapi`, `starlette`, `pydantic`, `asyncpg`, `app.core`.
- `forbidden`: `app.<A>.*` не импортирует `app.<B>.dao`, `app.<B>.controller`, `app.<B>.handler` для A ≠ B.
- `forbidden`: `app.common` не импортирует ни один модуль; `app.core` — ни один предметный модуль (`app.common` ему разрешён: ошибки `AppError` нужны `core/http_errors.py`).
- `layers` между модулями: `result | reminder` > `vote` > `idea | auth` > `contest | user`; `app.notification` и `app.realtime` не импортируют предметные модули.
- `app.core.testing` (тестовые часы для e2e) никем не импортируется, кроме `app.main`, который подключает его только при `APP_ENV=e2e`.
- Циклических импортов нет; относительные импорты выше пакета запрещены (ruff `TID252`).

Frontend: `pages → features → api | shared`; `features/*` не импортируют друг друга; `fetch` и
`WebSocket` — только в `src/api`; `Date.now()` — только в `shared/lib/serverTime.ts`
(проверяют ESLint и dependency-cruiser).

### 4.3 Владельцы побочных эффектов

| Побочный эффект | Единственный владелец |
|---|---|
| Транзакция БД (begin/commit, повтор при дедлоке) | `core/db.py::run_in_transaction`, вызывает только `service` |
| Чтение времени | `core/clock.py::Clock`; `model` получает `now` аргументом |
| Публикация события | `service` модуля, **после** commit, через `realtime.service` |
| Постановка письма | `service` модуля, **внутри** транзакции, через `notification.service` (outbox) |
| Отправка SMTP | `notification/handler` (тик и событие «есть письма») → `notification/service` |
| Финализация, напоминания | `core/scheduler.py` вызывает `result/handler`, `reminder/handler` → их `service` |
| Перевод ошибок в HTTP | `core/http_errors.py` (по `code`/`status` исключения); особые случаи — `handler` модуля |
| Перевод ошибок БД в доменные | `dao` модуля (по имени constraint) |

### 4.4 Куда класть новый код

| Изменение | Куда |
|---|---|
| Новая сущность или понятие | `app/<модуль>/model/<сущность>.py`; модуль — тот, кто владеет сущностью; нет подходящего — новый модуль со всеми шестью слоями и запись в §17 |
| Новое правило «кто/когда может» | `app/<модуль>/model/policy.py` + unit-тест на границы; если видно в UI — поле `allowed_actions` |
| Новая ошибка | `app/<модуль>/exception/errors.py`: наследник `AppError` с `code` и `status` + реэкспорт в `__init__` |
| Новый сценарий записи | функция в `app/<модуль>/service/`, транзакция через `run_in_transaction` |
| Новый SQL | `app/<модуль>/dao/`; изменение схемы — миграция Alembic |
| Новый эндпоинт | `app/<модуль>/controller/` + схема там же + политика доступа + регенерация контракта |
| Новое письмо | шаблон в `app/notification/service/templates.py` + `EmailKind` + `dedup_key` вида `<kind>:<contest>:<user>` + постановка из `service` модуля-источника |
| Новая периодическая задача | функция в `service` модуля, вызов из его `handler`, регистрация в `core/scheduler.py` (не новый процесс и не новый контейнер) |
| Новое WS-событие | `EventType` в `app/realtime/model/event.py`, правило адресатов в `model/policy.py` публикующего модуля (§4.2), обработчик в `frontend/src/api/events.ts` |
| Новый экран | `frontend/src/pages/` + логика в `features/<фича>/` |
| Переиспользуемый UI | `shared/ui/` — только со второго использования |
| Лимит или длина поля | константа в `model` модуля (`TITLE_MAX_LENGTH` в `idea/model/idea.py`) + CHECK в миграции |
| Общий тип или проверка для нескольких модулей | `app/common/model/` — только со второго реального использования |

---

## 5. Стек и допустимые зависимости

| Слой | Выбор | Почему |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, pydantic-settings, uvicorn | Предпочтителен по ТЗ; нативные async и WebSocket; авто-OpenAPI |
| БД | PostgreSQL 16, SQLAlchemy 2.0 (async), asyncpg, Alembic | Явные транзакции и блокировки; версионируемые миграции |
| Безопасность | argon2-cffi, email-validator, limits, stdlib `secrets`/`hashlib`/`hmac` | Поддерживаемые библиотеки, без самописной криптографии |
| Почта | aiosmtplib | Async SMTP |
| Логи | structlog (JSON) | Привязка `request_id` через contextvars |
| Frontend | React 18, TypeScript, Vite, react-router, @tanstack/react-query, openapi-fetch | Требование ТЗ; типы из OpenAPI |
| Тесты | pytest, pytest-asyncio, httpx, hypothesis, pytest-randomly; Vitest, Testing Library, MSW; Playwright | §10 |
| Качество | uv, ruff, mypy, import-linter, pip-audit; Prettier, ESLint (typescript-eslint), tsc, dependency-cruiser, openapi-typescript; gitleaks | §6, §13 |
| Инфраструктура | Docker Compose ≥ 2.20, postgres:16, Mailpit | §11–§12 |

**Запрещено добавлять без записи в журнал и обоснования** «зачем / почему без этого нельзя / лицензия»:
Redis, Celery, APScheduler, брокеры сообщений, nginx, отдельный контейнер frontend, UI-киты,
state-менеджеры, библиотеки дат и форм. Любая новая зависимость = строка в §17 и проверка в DoD.

---

## 6. Code style и поддерживаемость

### 6.1 Инструменты и команды (backend проверено в IC-002; frontend, `make check` — план)

| Что | Python (`backend/`) | TypeScript (`frontend/`, `e2e/`) |
|---|---|---|
| Версии | Python 3.12 через `uv`, `uv.lock`, `.python-version` | Node 22 LTS, `package-lock.json`, `.nvmrc` |
| Установка | `uv sync --frozen` | `npm ci` |
| Формат | `uv run ruff format --check .` (line-length 100) | `npm run format:check` (Prettier) |
| Линт | `uv run ruff check .` (наборы `E,F,W,I,B,UP,SIM,RUF,DTZ,S,BLE,T20,TID,ASYNC,PT,N,ERA`) | `npm run lint` (ESLint `strictTypeChecked`, react-hooks, jsx-a11y, `react/no-danger`) |
| Типы | `uv run mypy --strict app tests` | `npm run typecheck` (`tsc --noEmit`, `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) |
| Границы | `uv run lint-imports` | `npm run depcruise` |
| Всё сразу | `make check` | входит в `make check` |

### 6.2 Обязательные правила (каждое проверяется)

| Правило | Как проверяется |
|---|---|
| Имя функции = глагол + предмет: `cast_vote`, `rank_ideas`, `enqueue_due_reminders` | ревью; запрещены `utils.py`, `helpers.py`, `process_*`, `handle_*` без предмета |
| Предикаты `is_/can_/has_` возвращают `bool` и не бросают; `ensure_*` бросают доменную ошибку и ничего не возвращают; функции с I/O — `async` | mypy (возвращаемые типы), ревью |
| Единая терминология (глоссарий §6.4) в коде, API, UI и документах | ревью |
| Зависимости функции — явные аргументы (`session`, `clock`, `actor`), без глобального состояния | import-linter, ревью |
| Типы выражают допустимые состояния: `Phase` — `StrEnum`; `Actor` — frozen dataclass; `Optional` только где NULL осмыслен | mypy `--strict` |
| Naive `datetime` запрещён; `datetime.now`, `utcnow`, `time.time`, `time.sleep` вне `core/clock.py` запрещены | ruff `DTZ`, `TID251` banned-api |
| Нет молчаливого подавления: `except Exception: pass` запрещён; широкий `except` — только в цикле планировщика с логированием | ruff `BLE001`, `S110` |
| Технические ошибки → ошибки приложения: `IntegrityError` переводится в доменную ошибку по имени constraint; неизвестное → 500 `internal_error` без деталей | api-тесты на формат ошибок |
| Комментарий объясняет «почему» (почему `FOR SHARE`, почему 404 вместо 403), не «что» | ревью |
| Общая абстракция — только при втором реальном использовании | ревью |
| Секреты — `SecretStr`; в логах нет паролей, токенов, cookie, e-mail (маскируется), текстов идей | gitleaks; тест `caplog` |
| `print` запрещён | ruff `T20` |
| TS: `no-floating-promises`, `switch-exhaustiveness-check` по `phase`, `code`, типу события; `dangerouslySetInnerHTML` запрещён | ESLint |

### 6.3 Примеры размещения и имён

| Логика | Где | Хорошо | Плохо |
|---|---|---|---|
| Фаза из времени | `contest/model/contest.py` | `ContestSchedule.phase_at(now) -> ContestPhase` | `get_status()` |
| Можно ли голосовать | `vote/model/policy.py` | `can_vote(actor, idea, phase) -> bool`, `ensure_can_vote(...) -> None` | `check_vote()` (неясно: bool или исключение) |
| Победитель | `result/model/ranking.py` | `rank_ideas(scores) -> tuple[RankedIdea, ...]` | логика в контроллере |
| Кому напомнить | `reminder/model/reminder.py` | `select_reminder_recipients(employees, participants)` | SQL в домене |
| Голос в транзакции | `vote/service/` | `cast_vote`, `withdraw_vote` | `session.commit()` в роутере |
| SQL подсчёта | `vote/dao/` | `count_votes_by_idea(session, contest_id)` | |
| Схема ответа | `idea/controller/schemas.py` | `IdeaForVoting` (нет полей автора), `IdeaWithAuthor` | одна схема с `author=None` |
| React-хук | `features/voting/` | `useCastVote`, `contestKeys.ideas(id)` | `useData` |

### 6.4 Глоссарий

| RU | Код и API | Значение |
|---|---|---|
| конкурс | `contest` | тема + два дедлайна |
| раунд | `round`: `submission` \| `voting` | период приёма или голосования (напоминания) |
| фаза | `phase`: `submission` \| `voting` \| `finished` | вычисляется из `now` и дедлайнов |
| идея / голос | `idea` / `vote` | |
| организатор / сотрудник | `organizer` / `employee` | роли |
| автор / голосующий | `author` / `voter` | роли пользователя относительно идеи |
| финализация | `finalization` | разовая фиксация итога и постановка писем |
| участник | `participant` | автор текущей идеи или голосующий в конкурсе |

### 6.5 Самопроверка уровня Senior (обязательна для каждого написанного кода)

Требование владельца (2026-10-20 05:31): каждый написанный код до коммита проверяется так, будто его
ревьюит Senior-разработчик: **безопасность, структура, архитектура, корректность**. Найденное
исправляется до коммита; то, что осознанно не исправлено, записывается как известное ограничение.

| Ось | Что проверить |
|---|---|
| Безопасность | Ввод проверяется на границе (схема) и инварианты — в модели; нет утечки персональных данных и связки автор ↔ идея в логи, `repr`, тексты ошибок и события; права проверяются на сервере, порядок 401 → 404 → 403 → 409; SQL только с параметрами; секретов нет в коде и тестах; новая зависимость проверена (`pip-audit`, лицензия) |
| Структура | Файл в нужном модуле и слое (§4.4); имена по §6.2 и глоссарию §6.4; нет дублирования и мёртвого кода; комментарии объясняют «почему»; публичное API пакета — через `__init__` и `__all__` |
| Архитектура | Импорты по §4.2 (внутри модуля и между модулями, без циклов); побочные эффекты только у владельцев §4.3; решения Р1–Р14 не нарушены; нет новой инфраструктуры без записи в §17 |
| Корректность | Каждое поведение привязано к требованию ТЗ (§1); границы: `d−1µs / d / d+1µs`, пусто / максимум / максимум+1, часовые пояса и naive `datetime`, повтор запроса, гонка двух вкладок; на каждую ветку есть тест; `ruff`, `mypy --strict`, `pytest` зелёные |

Где фиксируется результат:
1. `docs/code-review/<ГГГГ-ММ-ДД>-<тема>.md` — что проверено по каждой оси, найденные проблемы, как исправлены, что осталось и почему, какие команды запускались и с каким итогом.
2. Тело коммита — краткий итог самопроверки (найдено / исправлено / осталось) и ссылка на файл.
3. §17 — строка, если самопроверка изменила решение или правило.

---

## 7. База данных

### 7.1 Сущности, ключи, ограничения

| Таблица | Ключ | Основные поля | Ограничения и индексы | Владелец |
|---|---|---|---|---|
| `users` | bigint identity | email, name, password_hash, role, is_active, created_at | `UNIQUE(lower(email))`, `CHECK role IN ('employee','organizer')` | `user` |
| `sessions` | bigint identity | token_hash bytea, user_id, created_at, expires_at, revoked_at NULL | `UNIQUE(token_hash)`; FK users CASCADE; idx(user_id), idx(expires_at) | `auth` |
| `contests` | bigint identity | topic, description, submission_deadline, voting_deadline, created_by, created_at, finalized_at NULL, winner_idea_id NULL | `CHECK submission_deadline < voting_deadline`; `CHECK (winner_idea_id IS NULL OR finalized_at IS NOT NULL)`; частичный idx(voting_deadline) WHERE finalized_at IS NULL | `contest`; `finalized_at`, `winner_idea_id` — `result` |
| `ideas` | **uuid** `gen_random_uuid()` | contest_id, author_id, title, description, submitted_at, updated_at, version int, client_request_id uuid, request_hash bytea | FK contests RESTRICT, users RESTRICT; CHECK длины title 1–200, description ≤ 10 000; `UNIQUE(author_id, client_request_id)`; idx(contest_id, submitted_at, id) | `idea` |
| `votes` | PK `(idea_id, voter_id)` | created_at | FK ideas **ON DELETE CASCADE**, users RESTRICT; idx(voter_id) | `vote` |
| `reminders` | PK `(contest_id, round, user_id)` | created_at | `CHECK round IN ('submission','voting')`; FK contests CASCADE | `reminder` |
| `outbox_emails` | bigint identity | dedup_key, kind, user_id NULL, to_email, subject, body NULL, status, attempts, next_attempt_at, lease_until NULL, not_after NULL, sent_at NULL, last_error NULL, created_at | `UNIQUE(dedup_key)`; `CHECK status IN ('pending','sending','sent','failed','expired')`; частичный idx(next_attempt_at) WHERE status IN ('pending','sending') | `notification`: пишут `service` других модулей через `notification.service`, отправляет `notification/handler` |

- Результаты **не хранятся**: считаются `COUNT … GROUP BY` при каждом запросе (нет счётчиков → нет потерянных обновлений). `winner_idea_id` фиксируется при финализации только для писем; результаты API и письма считаются одной функцией `rank_ideas` (`result/model/ranking.py`) (integration-тест сверяет).
- **Время:** все поля `timestamptz` (микросекунды, UTC); сессия БД `timezone=UTC`. API принимает время только со смещением. Деньги и дробные числа — N/A.
- **NULL-семантика:** `finalized_at IS NULL` — финал не выполнен; `finalized_at` есть, `winner_idea_id IS NULL` — идей не было; `revoked_at` — выход; `not_after` — письмо теряет смысл после момента; `client_request_id IS NULL` — старый клиент без ключа (дубли NULL допустимы осознанно).
- `submitted_at` ставится один раз при создании; правка меняет только `updated_at` и `version` (П10).

### 7.2 Транзакции и конкурентность

Уровень `READ COMMITTED`, порядок блокировок **contest → idea → vote**, `now` читается **после** блокировок.
Все транзакции записи идут через `run_in_transaction`: на `40P01`/`40001` — повтор до 3 раз с джиттером,
`now` читается заново, события и внешние эффекты — только после последнего успешного commit.

| Операция | Шаги транзакции | Ошибки |
|---|---|---|
| Подать идею | поиск по `(author_id, client_request_id)` → найдено: `request_hash` совпал → 200 с идеей, иначе 422 `idempotency_key_reused` → роль → `contest FOR SHARE` → now → фаза → лимиты → `INSERT … ON CONFLICT DO NOTHING RETURNING` → пусто: SELECT и та же проверка hash | 403, 404, 409 `submission_closed`, 409 `idea_limit_reached`/`contest_full` |
| Править идею | `contest FOR SHARE` → `idea FOR UPDATE` (нет или не автор → 404) → поля равны присланным → 200 → now → фаза → `version` ≠ присланной → 409 `stale_version` → `UPDATE … SET version = version + 1` | 404, 409 `submission_closed`, 409 `stale_version` |
| Удалить идею | `contest FOR SHARE` → `idea FOR UPDATE` (404) → now → фаза ≠ `finished` → `DELETE` (голоса каскадом) → после commit `idea_deleted` | 404, 409 `idea_locked` |
| Проголосовать | видимость идеи (404) → роль (403) → `contest FOR SHARE` → `idea FOR SHARE` → автор ≠ голосующий (403 `own_idea_vote`) → now → фаза → `INSERT … ON CONFLICT DO NOTHING` → 204 | 404, 403, 409 `voting_closed` |
| Отозвать голос | видимость → роль → `contest FOR SHARE` → now → фаза → `DELETE` (0 строк — тоже 204) | 404, 403, 409 |
| Финализировать | `contest FOR UPDATE` → now ≥ `voting_deadline` → `UPDATE … WHERE finalized_at IS NULL RETURNING` → ранжирование → outbox `ON CONFLICT DO NOTHING` | — (no-op при повторе) |
| Напомнить | для раундов с `deadline − 24h ≤ now < deadline`: `INSERT INTO reminders … SELECT … FROM users WHERE role='employee' AND is_active AND NOT EXISTS(участие) … ON CONFLICT DO NOTHING RETURNING` → outbox для вставленных, `not_after = deadline` | — |

Порядок проверок в каждом запросе: **аутентификация (401) → видимость объекта (404) → роль/политика (403) → фаза (409) → запись**. Иначе ответ раскрывает существование чужой идеи.

Гонки (подробно — `docs/edge-cases.md`): удаление ‖ голос → нет «сиротских» голосов, голос получает 404;
две вкладки → одна строка; голос на границе ‖ финализация → голос либо в итоге, либо 409.
Лимиты 20 идей на автора и 1000 на конкурс — **мягкие**: параллельные вставки под `FOR SHARE` могут
превысить их на единицы; корректность итога это не нарушает.

### 7.3 Пул, таймауты, недоступность

- Пул SQLAlchemy/asyncpg: `pool_size=10`, `max_overflow=5`, `pool_timeout=5s`, `pool_pre_ping=True`, `pool_recycle=1800`; плюс одно выделенное соединение под singleton-lock (не из пула).
- `server_settings`: `statement_timeout=5s`, `lock_timeout=2s`, `idle_in_transaction_session_timeout=30s`, `application_name=ideas-app`.
- Старт: ожидание БД до 60 с, затем выход с понятным сообщением. В работе: 503 `service_unavailable` + `Retry-After`, `/api/health` = 503, планировщик пропускает тик. Записи внутри запроса автоматически не повторяются, кроме дедлоков (выше).

### 7.4 Миграции

- Alembic, `transaction_per_migration=True`. Порядок запуска (python-лаунчер `app/core/launcher.py` (+ `core/singleton.py`) вместо shell-entrypoint; реализовано в IC-006): **сначала** взять singleton advisory lock (§12.2), **затем** применить миграции и стартовать сервер — иначе второй экземпляр (`compose run`, локальный uvicorn, другой checkout) успел бы мигрировать общую БД под работающим `app`. `lock_timeout=5s`; вручную — `make migrate` (`exec`, не `run`).
- **Expand/contract:** миграция либо только добавляет (таблица, nullable-колонка или с default, индекс), либо только удаляет то, что не использует **предыдущая** версия приложения. Версия N обязана работать на схеме N+1. Перенос данных — отдельная миграция, батчами, идемпотентно.
- Откат приложения на версию до expand-миграции безопасен; откат contract-миграции = восстановление из бэкапа.
- Если приложение видит в `alembic_version` неизвестную ему ревизию (например, после `git checkout` на ранний этап), лаунчер завершается с сообщением «БД на ревизии X, приложению известна Y». Флаг обхода не вводится (локальный объём); для прода — план в runbook.
- Индексы на больших таблицах — `CREATE INDEX CONCURRENTLY` вне транзакции.
- CI: пустая БД → `upgrade head` → `alembic check` (модели = схема) → `downgrade -1` → `upgrade head`.

### 7.5 Бэкап, восстановление, хранение

- `make backup` (план) → `pg_dump -Fc` в `backups/` (в `.gitignore`, права 600: в дампе ПДн и авторство).
- `make restore-check` (план) → восстановление в `ideas_restorecheck` того же контейнера `db`, сверка ревизии схемы и числа строк, удаление. Восстановление считается рабочим только после этой проверки (шаг CI).
- `make restore` (план) → остановить `app` → восстановить → `make up`; подтверждение вводом имени проекта.
- Хранение: истёкшие сессии удаляются ежедневно; `outbox_emails.body` → NULL через 30 дней после `sent/failed/expired`; идея удаляется физически (так требует ТЗ); пользователи не удаляются — деактивация (`is_active=false`, отзыв сессий), при запросе — обезличивание. Локально хранить 7 последних бэкапов.
- Чувствительные данные: e-mail, имена, хэши паролей, авторство идей до финала, кто за что голосовал (не раскрывается никому, включая организатора).

---

## 8. API и фоновые задачи

### 8.1 Общие правила
- Префикс `/api`, без версии в пути: SPA и API выкатываются одним образом. Совместимость — только аддитивные изменения; заголовок `X-App-Build` в ответах и в приветствии WS, при расхождении SPA предлагает обновить страницу.
- Источник контракта — OpenAPI, генерируемый FastAPI. `make contract` (план) на хосте через `uv run` (без контейнеров, `create_app` собирается без БД) → `frontend/openapi.json` → `openapi-typescript` → `frontend/src/api/schema.gen.ts`. В CI — регенерация и `git diff --exit-code`. Ручных TS-типов ответов нет.
- Ошибки — `application/problem+json`: `{type, title, status, code, detail, request_id, errors[]}`. `code` — стабильный lower_snake_case, фронт ветвится только по нему; `title` — понятный пользователю текст; 500 → `internal_error` без стека и SQL; 422 FastAPI переупаковывается в тот же формат; `Retry-After` для 429/503.
- Коды: 400 неверный JSON; 401 нет/истекла сессия; 403 роль или правило; **404 — объекта нет или он недоступен актору**; 409 фаза/версия/лимит; 413 тело > 64 КБ; 415 тело не JSON; 422 валидация; 429 лимит; 503 БД недоступна.
- Тело запроса — JSON (обязателен `Content-Type: application/json`, только если тело не пустое).
- `GET /api/contests/{id}` возвращает `phase`, `server_time`, `allowed_actions` (фронт не дублирует правила фаз) и текст правила ничьей.
- Пагинация: `GET /api/contests?limit≤100&offset`, сортировка `voting_deadline DESC, id DESC`. Список идей конкурса отдаётся целиком (≤ 1000 по лимиту записи).
- Валидация: NFC, trim, запрет управляющих и невидимых символов (кроме `\n`, `\t` в описании), длины из констант `model` модуля (`idea/model/idea.py`, `contest/model/contest.py`), проверка — `common/model/text.py`, `extra="forbid"`, даты только со смещением.
- `Cache-Control: no-store` для `/api/*` (проверено в IC-004; реализовано `core/middleware.py`, `core/http_errors.py`, `core/access.py`).

### 8.2 Эндпоинты (план)

| Метод и путь | Кто | Успех | Ошибки |
|---|---|---|---|
| `POST /api/auth/register` | аноним | 201 | 422, 409 `email_taken`, 429 |
| `POST /api/auth/login` / `POST /api/auth/logout` / `GET /api/auth/me` | аноним / вошедший | 200 / 204 / 200 | 401 `invalid_credentials`, 429 |
| `GET /api/contests` | вошедший | 200 `{items,total}` | 401 |
| `POST /api/contests` | организатор | 201 | 403, 422 `deadlines_order` (`DeadlinesOrderError`), `invalid_contest` (тема или описание), `deadline_in_past` |
| `GET /api/contests/{id}` | вошедший | 200 | 404 |
| `GET /api/contests/{id}/ideas` | вошедший | 200: подача — свои; голосование — все без автора и времени + `is_mine`, `my_vote`; финал — с авторами | 404 |
| `POST /api/contests/{id}/ideas` | сотрудник | 201 (повтор — 200) | §7.2 |
| `PATCH /api/ideas/{id}` | автор | 200 | §7.2 |
| `DELETE /api/ideas/{id}` | автор | 204 | 404, 409 `idea_locked` |
| `PUT` / `DELETE /api/ideas/{id}/vote` | сотрудник | 204 | 404, 403, 409 |
| `GET /api/contests/{id}/results` | организатор (без авторов до финала), все после финала | 200 | 403 `results_not_published` |
| `GET /api/organizer/contests/{id}/dashboard` | организатор | 200 `{ideas_count, voters_count, results[]}` | 403 |
| `WS /api/contests/{id}/events` | вошедший | `{"v":1,"type":…,"contest_id":…,"idea_id"?}` | закрытие 4401/4403 |
| `GET /api/health` | все | 200 `{"status":"ok"}` / 503 | — |
| `POST /api/__test__/clock` | только `APP_ENV=e2e` | 204 | 400 (время только вперёд) |

События WS: `ideas_changed`, `idea_deleted`, `results_changed`, `session_revoked`. Событие
`phase_changed` не вводится (IC-001, предложено): фаза меняется по времени, а не по действию, поэтому
публиковать его некому; клиент сам перечитывает данные в момент дедлайна по `server_time`
(тип `PHASE_CHANGED` удаляется из `realtime/model/event.py` в IC-024).
Адресатов вычисляет публикующий сервис по политике своего модуля (§4.2): в фазе подачи события об идее — только автору и организатору;
`idea_deleted` всем — только в фазе голосования; `results_changed` — только организатору.

### 8.3 Идемпотентность и неизвестный результат
- `PUT`/`DELETE` голоса идемпотентны по природе (204 всегда).
- Создание идеи — `client_request_id` (UUID, генерирует SPA) + `request_hash` (включает `contest_id`, `title`, `description`); поиск по ключу **до** проверки фазы, чтобы повтор после таймаута на дедлайне вернул принятую идею, а не 409.
- Правка — повтор с теми же полями возвращает 200 (проверка до фазы и версии).
- Обрыв соединения на COMMIT → клиент получает ошибку и безопасно повторяет: все записи идемпотентны.
- SPA повторяет только идемпотентные запросы, не более 2 раз, в пределах 10 с общего бюджета; при 4xx не повторяет.

### 8.4 Фоновые задачи
- Один asyncio-цикл в процессе приложения, тик 15 с и сразу при старте; каждый тик под `pg_try_advisory_xact_lock` (не получилось — пропуск). Корректность держат условные `UPDATE` и уникальные ключи, lock только экономит работу. Webhook — N/A (входящих интеграций нет).
- **Финализация** и **напоминания** — §7.2. Порядок задач не важен: каждая идемпотентна.
- **Outbox-отправщик**: просыпается сразу после commit (событие шины) и по тику; берёт до 20 писем `FOR UPDATE SKIP LOCKED` с арендой 60 с; `not_after < now` → `expired`; SMTP с таймаутом 10 с и детерминированным `Message-ID`; успех → `sent`; сетевая ошибка или 4xx → `pending` с backoff `min(2^attempts мин, 1 ч)`; 5xx или 8 попыток → `failed`.
- **Гарантии:** создание письма — exactly-once; доставка — at-least-once (падение между SMTP 250 и commit даёт повтор после аренды).
- **Восстановление:** первый тик при старте догоняет пропущенное; незавершённые письма возвращаются по аренде.
- **Завершение:** перестать брать новое, дождаться текущего письма ≤ 10 с, тик откатывается.

---

## 9. Аутентификация, авторизация, безопасность

### 9.1 Проверка личности
- **Вход:** e-mail + пароль (ТЗ оставляет на усмотрение, e-mail нужен для писем). Пароль — Argon2id (`argon2-cffi`, параметры OWASP: m=19 МиБ, t=2, p=1), `check_needs_rehash` при входе, хэширование в пуле потоков под семафором на 4 одновременных. Для неизвестного e-mail выполняется проверка по фиктивному хэшу (одинаковое время ответа). Пароль 10–128 символов, NFKC перед хэшированием.
- **Регистрация:** открыта для сотрудников с e-mail из `ALLOWED_EMAIL_DOMAINS`. Подтверждение e-mail, восстановление по почте и MFA — **N/A в этом объёме** (Р11; в проде — SSO компании). Сброс пароля оператором: `make cli ARGS="reset-password <email>"` (через `exec`), отзывает сессии.
- **Организатор** создаётся при первом запуске из `ORGANIZER_EMAIL`/`ORGANIZER_PASSWORD` (идемпотентно). В `APP_ENV=prod` старт отклоняется, если пароль короче 16 символов или совпадает с `.env.example`.
- **Сессии:** токен `secrets.token_urlsafe(32)`, в БД — SHA-256. Cookie `sid`: `HttpOnly; SameSite=Lax; Path=/`, в проде `__Host-sid` и `Secure`. Абсолютный срок 7 дней, без продления. При входе — всегда новый токен. Выход — `revoked_at` + удаление cookie + событие `session_revoked` (закрывает WS этой сессии). Отзыв через CLI — REST сразу 401, открытые WS перепроверяют сессию раз в 60 с.
- Роль и `is_active` не кэшируются: каждый запрос делает `sessions JOIN users` с условиями `revoked_at IS NULL AND expires_at > :now AND is_active`. Изменение прав действует со следующего запроса.

### 9.2 Проверка прав
- **Default deny:** каждый маршрут объявляет политику через зависимость; маршрут без политики — ошибка запуска. Явный allow-list публичных маршрутов: `/api/health`, `/api/auth/login`, `/api/auth/register`, статика SPA и fallback на `index.html` (все пути вне `/api`). `POST /api/__test__/clock` имеет политику `e2e_only`. Тест перечисляет `app.routes` и падает на маршруте без политики и вне allow-list.
- Политики — чистые функции `<модуль>/model/policy.py`: `can_view_idea`, `can_edit_idea`, `can_delete_idea`, `can_vote`, `can_view_results`, `can_view_authors`, `event_recipients`. В SQL дополнительно `WHERE author_id = :actor_id` для правки и удаления.
- Чужой невидимый объект → 404. Организатор подаёт/голосует → 403 `organizer_cannot_participate`.
- Мультиарендность — N/A (одна компания).

### 9.3 Риски и меры

| Риск | Мера |
|---|---|
| Утечка авторства до финала | Схемы по фазе без автора и времени (`extra="forbid"`, точный набор ключей в contract-тесте); UUIDv4 и `ORDER BY id`; счётчики только организатору; события о чужих идеях в фазе подачи не отправляются; организатор до финала видит результаты без авторов; ошибка `own_idea_vote` раскрывает авторство только самому автору |
| Утечка результатов до финала | Единственная функция `can_view_results` для REST и WS |
| Накрутка голосов | PK голосов, запрет за свою, организатор не голосует. Остаточный риск: лишние аккаунты (Sybil) при саморегистрации |
| Обход дедлайна | Фаза на сервере после блокировки; `now` перечитывается при повторе |
| SQL-инъекции | Только SQLAlchemy с параметрами; `text()` только с bind-параметрами; ruff `S608` |
| XSS | React экранирует; `dangerouslySetInnerHTML` запрещён; описание — простой текст (`white-space: pre-wrap`); CSP `default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`; `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` |
| Инъекции в письма | Plain text; заголовки через `email.message.EmailMessage`; управляющие символы запрещены на входе |
| CSRF | `SameSite=Lax` + `Origin` ∈ `ALLOWED_ORIGINS` для небезопасных методов (нет `Origin` → 403) + JSON-тела. `http://localhost:5173` в списке только при `APP_ENV=dev` |
| CSWSH | Проверка `Origin` при рукопожатии WS до `accept` |
| SSRF | N/A — сервер не ходит по URL из пользовательских данных |
| Загрузка файлов | N/A — `multipart/form-data` отклоняется 415 |
| Перебор паролей | `limits` in-memory: вход 5 / 15 мин на (e-mail, IP); регистрация 5 / ч на IP; блокировки аккаунта нет. Отключение per-IP лимита разрешено валидацией только при `APP_ENV=e2e` |
| Злоупотребление ресурсами | Тело ≤ 64 КБ; лимиты идей; ≤ 10 WS на пользователя; входящие WS-сообщения ≤ 1 КБ (только ping) |
| Тестовые часы в проде | Маршрут регистрируется только при `APP_ENV=e2e` и имени БД с суффиксом `_e2e`; часы только вперёд |
| Утечка через `/api/health` | Отдаёт только статус, без версий и причин |

### 9.4 Секреты
- Секреты: пароль БД в `DATABASE_URL`, `ORGANIZER_PASSWORD`, `SMTP_*`. Ключей подписи нет (токены случайные, в БД хэш) — нечего ротировать и нечем подделать.
- Загрузка через pydantic-settings, тип `SecretStr`. `.env` в `.gitignore`; `.env.example` — только заглушки с пометкой «dev only». gitleaks в CI.
- Ротация: пароль БД — смена в env + перезапуск; массовый отзыв сессий — `make cli ARGS="revoke-sessions --all"`.

---

## 10. Стратегия тестирования

### 10.1 Уровни

| Уровень | Что проверяет | Инфраструктура | Правила |
|---|---|---|---|
| **Unit** (`tests/unit`, `pytest -m unit`) | `app/*/model`: фазы на границах `d−1µs/d/d+1µs`, таблица истинности политик (3 фазы × роль × свой/чужой), ранжирование (Hypothesis: результат не зависит от порядка входа), выбор получателей напоминаний, валидация, лимитер | Без БД и сети; `FrozenClock`, инжектируемая случайность | < 5 с на весь набор |
| **Integration** (`tests/integration`, `tests/api`, `pytest -m integration`) | SQL, ограничения, транзакции и блокировки, гонки, миграции, сервисы, HTTP через `httpx.AsyncClient(ASGITransport)`, планировщик через `run_tick(now)` | Реальный PostgreSQL: локально БД `ideas_test` в существующем контейнере `db` (127.0.0.1:5433), в CI — service-контейнер; адрес задаёт `TEST_DATABASE_URL` (IC-005). Изоляция savepoint (`join_transaction_mode="create_savepoint"`); тесты с реальным commit — маркер `commits` + TRUNCATE | conftest отказывается работать с БД без суффикса `_test`; планировщик и singleton-lock выключены флагами настроек |
| **Contract** (`tests/contract`, `make test-contract`) | Снимок OpenAPI (`frontend/openapi.json`, версия = коммит), сгенерированные TS-типы (`tsc`), точные наборы ключей ответов по фазам и ролям, схемы WS-событий с полем `v`, фикстуры MSW проходят по типам из `schema.gen.ts` | Без сети | Источник контракта — OpenAPI из `create_app`; версия — git-коммит |
| **E2E** (`e2e/`, `make e2e`) | Критические сценарии ТЗ: подача → голосование → финал; две вкладки (П5); открытая страница после дедлайна (П2); удаление идеи исчезает у другого (П11); экран организатора меняется (П7); письма в Mailpit (Ф4) | Единственный `app` в режиме e2e, БД `ideas_e2e`, тестовые часы, Mailpit API | Ожидание по условию (`expect(...).toHaveText`), `waitForTimeout` запрещён |

### 10.2 Моки внешних сервисов
- Единственная интеграция — SMTP. Порт `EmailSender`; в unit/integration — `FakeMailSender` с режимами: успех, отказ 4xx/5xx, таймаут, обрыв соединения, некорректный ответ, «отправлено, но commit упал». Тесты проверяют получателя, заголовки (`Message-ID`), повторы и backoff.
- Mailpit используется только в e2e. Ни мок, ни Mailpit не доказывают работу реального почтового провайдера — записано в README.
- Ни один автоматический тест не обращается к реальным внешним сервисам и не использует рабочие секреты (`.env.test` с фиктивными значениями).

### 10.3 Обязательные правила
- Каждая функция с бизнес-логикой имеет проверяемое поведение, покрытое тестом, включая границы и ошибки; допустима проверка через публичный интерфейс. Отдельные тесты приватных методов и тривиального делегирования не требуются.
- **Критические ветви** (обязательны, независимо от процента): каждая строка таблицы истинности политик, каждая граница дедлайна, каждая строка §7.2, каждое «Ожидаемое поведение» П1–П11 (§1).
- Покрытие веток: `app/*/model` и `app/auth` ≥ 95 %; общий процент — справочно.
- Каждый исправленный дефект → регрессионный тест `test_regression_<краткое_имя>` со ссылкой на запись журнала.
- Нет `sleep`: ruff `banned-api` на `time.sleep`/`asyncio.sleep` в `tests/`; ESLint на `waitForTimeout`. Конкурентность — `asyncio.Barrier`/`Event`.
- Независимость от порядка — `pytest-randomly`.

### 10.4 Команды (план, не запускались)

| Команда | Назначение | Ожидаемый результат |
|---|---|---|
| `make test-unit` | unit backend + Vitest | код 0, < 30 с |
| `make test-int` | создаёт `ideas_test` в `db` при отсутствии, `uv run pytest -m integration` | код 0 |
| `make contract` | экспорт OpenAPI на хосте (`uv run`, без БД) и генерация `schema.gen.ts` | файлы обновлены |
| `make test-contract` | `make contract` + `git diff --exit-code` + `tsc` + contract-тесты | код 0, нет diff |
| `make e2e` | переводит `app` в режим e2e, Playwright, `trap 'make up'` | код 0; после — `app` в режиме dev |
| `make test` | `test-unit` + `test-int` + `test-contract` (e2e — только явным `make e2e`, т.к. он переключает единственный `app`) | ненулевой код при любой ошибке |
| `make check` | `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`, Prettier, ESLint, `tsc`, `depcruise`, `test-contract` | код 0 |

---

## 11. Конфигурация и жизненный цикл

### 11.1 Требования к окружению
- Docker Desktop (Compose ≥ 2.20) — основной путь.
- Для разработки без контейнера приложения: `uv` (ставит Python 3.12; системный 3.9.6 не подходит), Node 22 LTS.
- Порты на хосте: `127.0.0.1:8000` (приложение), `127.0.0.1:8025` (Mailpit), `127.0.0.1:5433` (БД, только для тестов и psql).

### 11.2 Переменные окружения
Валидируются pydantic-settings при старте (`app.core.config.load_settings`, проверено unit-тестами IC-003); при ошибке — список всех проблем **без значений секретов**, выход с кодом 2. Пустая переменная считается неверным значением, а не отсутствующей: по умолчанию не подменяется. Пример значений для dev — `.env.example` (в prod его пароль организатора отклоняется).

| Переменная | Обязательна | Правило |
|---|---|---|
| `APP_ENV` | да | `dev` \| `e2e` \| `prod` (pytest использует свои настройки) |
| `DATABASE_URL` | да | `postgresql+asyncpg://…`; при `APP_ENV=e2e` имя БД оканчивается на `_e2e` |
| `ORGANIZER_EMAIL`, `ORGANIZER_PASSWORD`, `ORGANIZER_NAME` | да | prod: пароль ≥ 16 и не из `.env.example` |
| `ALLOWED_EMAIL_DOMAINS` | да | список доменов через запятую |
| `PUBLIC_BASE_URL` | да | prod: https; из него `ALLOWED_ORIGINS` |
| `SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM` | да | |
| `DISPLAY_TZ` | нет (`Europe/Moscow`) | валидный IANA-пояс; для писем |
| `SCHEDULER_INTERVAL_S` | нет (15) | 5–300 |
| `WEB_CONCURRENCY` | нет (1) | только 1, иначе отказ старта |
| `RUN_SCHEDULER`, `HOLD_SINGLETON_LOCK` | нет (true) | выключаются в тестах и CLI |
| `TEST_CLOCK_ENABLED` | нет (false) | true только при `APP_ENV=e2e` |
| `RATE_LIMIT_PER_IP_ENABLED` | нет (true) | false только при `APP_ENV=e2e` |
| `SEED_DEMO` | нет (false) | true только при `APP_ENV` = `dev`/`e2e` |
| `LOG_LEVEL`, `LOG_FORMAT` | нет (`INFO`, `json`) | |

Различия сред: **dev** — демо-данные, `:5173` в `ALLOWED_ORIGINS`, cookie без `Secure`; **test** (pytest) — БД `*_test`, без планировщика и lock; **e2e** — БД `ideas_e2e`, тестовые часы, без per-IP лимита, плашка «E2E MODE» в UI; **prod** (план) — https, `__Host-` cookie, HSTS, строгие пароли, без демо и тестовых маршрутов.

### 11.3 Команды жизненного цикла (`up`, `down`, `restart`, `logs`, `migrate`, `psql`, `test-unit`, `test-int`, `check` реализованы в IC-006, проверены CI; остальные — план)

| Команда | Назначение | Ожидаемый результат |
|---|---|---|
| `make up` | `scripts/up.sh`: проверка Docker и порта, preflight по label, создание `.env` из примера при отсутствии, `docker compose up -d --build --wait --remove-orphans`, postcheck | Ровно 1 контейнер приложения в режиме dev, `/api/health` = 200, URL в выводе |
| `make down` | `docker compose down` (**без `-v`**) | Контейнеры остановлены, volume `pgdata` цел |
| `make restart` | `down` + `up` | Простой 5–15 с |
| `make logs` | `docker compose logs -f --tail=200 app` | Поток JSON-логов |
| `make status` | контейнеры по label, режим, `app.cli status` (outbox, лаг планировщика, ближайший дедлайн) | Таблица состояния |
| `make migrate` | `docker compose exec app alembic upgrade head` | Схема на head |
| `make cli ARGS=…` | `docker compose exec app python -m app.cli …` | Результат команды CLI (модуль `app.cli` появится в IC-007) |
| `make psql` | `docker compose exec db psql …` | Консоль БД |
| `make backup` / `make restore-check` / `make restore` | §7.5 | Файл дампа / «восстановление проверено» / восстановленная БД |
| `make destroy` | удаление volume после ввода имени проекта | Данные удалены (только явно) |

Первый запуск: `make up` → лаунчер: lock → миграции → организатор из env → демо-данные при `SEED_DEMO=true`.

### 11.4 Health и завершение
- `GET /api/health` — readiness: `SELECT 1` ≤ 1 с, singleton-lock удержан, схема совместима → 200, иначе 503. Используется healthcheck Docker (через python, curl в slim-образе нет).
- **Graceful shutdown (SIGTERM):** health → 503 → uvicorn перестаёт принимать, `timeout_graceful_shutdown=10s` для активных запросов → планировщик останавливается между тиками → отправщик заканчивает текущее письмо → WS закрываются с кодом 1012 (клиенты переподключаются и перечитывают состояние) → закрывается singleton-соединение (lock снимается) → `engine.dispose()`.
- Docker: `init: true`, `stop_grace_period: 20s`, `restart: unless-stopped`.

### 11.5 Диагностика типичных ошибок запуска
Полная таблица — `docs/runbook.md`. Кратко: Docker не запущен; порт 8000 занят; конфликт имени контейнера (вывод, чей); БД не готова за 60 с; неверная конфигурация (список полей); неизвестная ревизия схемы; advisory lock занят другим процессом (адрес из `pg_stat_activity`).

---

## 12. Docker и инвариант одного контейнера приложения

### 12.1 Инвариант и область действия
**На одном Docker-хосте одновременно работает не более одного контейнера приложения этого проекта.**
- Контейнер приложения — `app` (backend + SPA). `db` (PostgreSQL) и `mailpit` — инфраструктура, не реплики приложения.
- Внутри контейнера — один процесс сервера (`uvicorn --workers 1`, проверяется при старте).
- Гарантии: (а) контейнеры на этом Docker-хосте — жёстко (имя контейнера); (б) любые процессы сервера, подключённые к той же БД (локальный uvicorn, IDE, `compose run`), — жёстко (advisory lock); (в) другие БД и хосты — вне области, обнаруживается только подсчётом по label.

### 12.2 Механизмы
1. **`container_name: ideas-competition-app`** + `name: ideas-competition` в `compose.yaml`. Демон атомарно откажет второму контейнеру с тем же именем: ловит `-p other`, `--scale app=2`, второй клон репозитория, параллельный `make up`.
2. **Session advisory lock** `pg_try_advisory_lock` на выделенном соединении (не из пула), берётся при старте сервера: повторы до 30 с (ждём, пока старый контейнер освободит при перезапуске), затем выход с сообщением «другой экземпляр приложения уже подключён к этой БД» и данными из `pg_stat_activity`. Проверка соединения каждые 10 с; потеря → перезахват; занят другим → health 503 и завершение. CLI в `exec` lock не берёт.
3. **Label `org.ideas-competition.role=app`** — не защита, а обнаружение: preflight в `up.sh` и `check_singleton.sh` считают контейнеры с label. Чужие контейнеры (другой project, `-run-`) **не удаляются**: выводятся с командами, которыми пользователь остановит их сам.

### 12.3 Правила
- Единственная поддерживаемая команда запуска — `make up`. Прямые `docker compose up` допустимы, инвариант держат механизмы выше.
- **`docker compose run` запрещён** для задач: миграции, CLI, psql — через `exec` в работающем контейнере.
- Отдельные тестовые compose-стеки запрещены (второй контейнер приложения). E2E — режим единственного `app` (Р14).
- Временные контейнеры инструментов (если понадобятся) — `docker run --rm` с label `org.ideas-competition.role=tool` и `trap 'docker rm -f …' EXIT`.
- Удаление volumes не входит ни в `down`, ни в `restart`, ни в очистку — только `make destroy` с подтверждением.
- Перезапуск = простой 5–15 с (blue/green невозможен по определению). Не перезапускать в последний час перед любым дедлайном; `make up` предупреждает, если ближайший дедлайн < 1 ч.
- Ресурсы: `app` — `mem_limit: 512m`, `cpus: 1.0`, `pids_limit: 256`; `db` — `512m`; логи `json-file` `max-size: 10m`, `max-file: 3`. Порты публикуются только на `127.0.0.1`.

### 12.4 Проверка инварианта — `scripts/check_singleton.sh` (план, в CI)
1. `make up` → контейнеров с label `role=app`: 1, запомнить ID.
2. `make up` повторно → 1, тот же ID.
3. `make up & make up; wait` → 1.
4. `docker compose -p other up -d app` → ошибка конфликта имени; итог 1.
5. `docker compose run --rm app` → сервер в нём не стартует (advisory lock); контейнер удалён.
6. Локальный `uv run uvicorn app.main:app` против той же БД → выход с сообщением о другом экземпляре.
7. Подсчёт: `docker ps -q --filter label=org.ideas-competition.role=app | wc -l` = 1.
8. `make down` → 0 контейнеров приложения; volume `ideas-competition_pgdata` существует.

---

## 13. Наблюдаемость, CI/CD, восстановление

- **Логи:** structlog, JSON в stdout: `ts, level, event, request_id, user_id, contest_id, route, status, duration_ms`; фоновые — `job, run_id, outbox_id`. `X-Request-ID` принимается при формате `^[A-Za-z0-9-]{1,64}$`, иначе генерируется; возвращается в ответе и в теле ошибки. Никогда не логируются пароли, токены, cookie, тела писем, тексты идей; e-mail маскируется (`a***@d.com`); связка автор ↔ идея в фазе голосования не пишется.
- **Метрики:** Prometheus — **N/A** (нет сервера сбора в локальном стеке). Вместо него — `duration_ms` в логах и `make status`: outbox pending/failed/возраст старейшего письма, лаг планировщика, пул, ближайший дедлайн.
- **Оповещения:** N/A локально. Оператор действует, если в `make status`: `failed` в outbox > 0 → смотреть `last_error`, проверить Mailpit; лаг планировщика > 2 мин → логи `job`; health ≠ 200 → §11.5.
- **Лимиты:** §12.3; пул 10 + 5; WS ≤ 10 на пользователя; outbox — пачка 20.
- **CI (GitHub Actions, план):**
  1. backend: `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`;
  2. frontend: `prettier --check`, `eslint`, `tsc --noEmit`, `depcruise`, `vite build`;
  3. тесты: unit + integration (service `postgres:16`), миграции (§7.4), contract (§8.1);
  4. зависимости и секреты: `pip-audit`, `npm audit --audit-level=high`, gitleaks;
  5. сборка образа, `make up`, `scripts/check_singleton.sh`, smoke (`/api/health`, вход организатора, `GET /api/contests`), `make backup && make restore-check`, `make e2e`, `make down`; при падении — артефакт `docker compose logs`.
  Раннер — отдельный одноразовый Docker-хост, инвариант соблюдается.
- **Выкладка (план для прода, не реализуется):** бэкап → образ с тегом git sha → остановка `app` → миграции (только expand) → старт → smoke → при неудаче вернуть предыдущий образ (схема совместима) → при порче данных — восстановление из бэкапа. Не выкладывать в последний час перед дедлайном.

---

## 14. Definition of Done для изменения

Изменение готово, только если **все** пункты выполнены:
1. Код лежит по §4.4; `lint-imports` и `depcruise` проходят; нет новых циклов.
2. Имена и обработка ошибок по §6; `ruff`, `mypy --strict`, ESLint, `tsc` без ошибок.
3. Каждый новый или изменённый маршрут имеет политику доступа; проверены 401/403/404 и порядок проверок §7.2.
4. Изменённые сценарии и существенные границы покрыты тестами нужного уровня (§10); для исправленного дефекта — регрессионный тест.
5. Тесты не обращаются к реальным внешним сервисам и не используют рабочие секреты.
6. При изменении схемы — миграция expand/contract, `alembic check`, проверка совместимости с предыдущей версией.
7. При изменении API — регенерирован контракт (`make test-contract` без diff).
8. `make check` и `make test` проходят; при затронутом запуске — `scripts/check_singleton.sh`.
9. Документация соответствует реализации: `CLAUDE.md`, `docs/*`, README («Состояние проекта»).
10. Нет необоснованных новых сервисов и зависимостей; новая зависимость записана в §17.
11. Отчётность: промпт в `docs/prompts.md`, решения в §17, коммит этапа (§16).
12. Проведена самопроверка уровня Senior по §6.5 (безопасность, структура, архитектура, корректность); результат — в `docs/code-review/` и в теле коммита; найденное исправлено или записано как известное ограничение.

---

## 15. Инструменты и AI (О7, С2, С7)

- **Инструмент:** Claude Code (агент Anthropic), запущенный из проекта claude.ai; работает с папкой проекта на компьютере владельца.
- **Модель:** Claude Opus 5.5 (`claude-opus-5-5`, контекст 1M токенов).
- **Почему:** агент сам читает и меняет файлы и запускает тесты, поэтому работоспособность будет доказываться прогоном тестов (их пока нет); большой контекст позволяет держать ТЗ, план и код одновременно.
- **Как шла работа над архитектурой (этап 2):** по запросу владельца запущены **три реальных субагента** (инструмент Agent в Claude Code): Architecture & Maintainability, Security & Quality, Data & Operations. Раунд 1 — независимые предложения; раунд 2 — взаимные контрпримеры; раунд 3 — проверка предварительных решений координатора по оставшимся разногласиям. Итоговые документы редактировал только координатор. Исходные отчёты — `docs/architecture-review/raw/`, сведение — `docs/architecture-review.md`.
- **Заимствования:** чужих решений и шаблонов не используется. Генераторы (например, `npm create vite`) записываются в журнал и README в момент использования.

## 16. Правила ведения отчёта

1. Каждый запрос владельца — дословно в `docs/prompts.md` с временем UTC.
2. Каждое решение — строка в §17 с временем UTC, причиной и номером требования.
3. Конец этапа: обновить статусы §1, «Состояние проекта» и «Следующим заходом» в README, строку в §18, коммит.
4. Экспорт сессии (`python3 tools/export_agent_session.py`) — после согласия владельца.
5. Историю git не переписывать (без squash и force-push). Единственное исключение — по прямой просьбе владельца 05:21 два первых коммита объединены в `2e305d0` до первой отправки на GitHub; после отправки история `main` не переписывается. В каждом MR — ровно один коммит (владелец, 06:14): правки по ревью объединяются с ним, и перезаписывается только ветка этого MR (`git push --force-with-lease`).
6. Использован генератор или чужой код — сразу запись в §15 и README.
7. Каждый написанный код проходит самопроверку §6.5; её результат — файл в `docs/code-review/`.
8. В `main` напрямую не пушится ничего (требование владельца 05:38): каждая задача — своя ветка и MR (pull request) в GitHub; мержит владелец после ревью; зелёный CI обязателен до мержа (06:09).
9. Задача IC-NNN начинается только после явного согласия владельца на эту задачу (06:12); готовность MR предыдущей задачи согласием не считается.

## 17. Журнал решений

Формат: время (UTC) — решение — причина — связь с ТЗ. Подробные обоснования решений этапа 2 — `docs/architecture-review.md`.

| Время (UTC) | Решение | Почему | ТЗ |
|-------------|---------|--------|----|
| 2026-10-20 04:25 | Папка проекта — `/Users/admin/PycharmProjects/IdeasCompetition` | Указал владелец | — |
| 2026-10-20 04:29 | Изучено ТЗ, составлен чек-лист трассировки (§1) | Каждое решение сверяется с ТЗ | все |
| 2026-10-20 04:30 | Работаем поэтапно, с согласованием каждого этапа | Просьба владельца «не писать всё сразу» | С4 |
| 2026-10-20 04:35 | Стек: Python 3.12 + FastAPI, PostgreSQL 16, React + TS + Vite | §5 | О2–О4 |
| 2026-10-20 04:35 | Фаза конкурса вычисляется из времени, а не хранится | Не может «не закрыться» | П1, П2 |
| 2026-10-20 04:35 | Уникальность голоса — ограничение БД | Защищает от гонок между вкладками | П5 |
| 2026-10-20 04:35 | ~~Реальное время — WebSocket + PostgreSQL LISTEN/NOTIFY~~ → пересмотрено 05:10 | | П7, П11 |
| 2026-10-20 04:35 | Почта — outbox в БД + Mailpit | Эмуляция внешнего сервиса | О10, Ф4, П9 |
| 2026-10-20 04:35 | Организатор не участвует в конкурсе | Видит результаты заранее | Ф5 |
| 2026-10-20 04:35 | ~~Вход по логину и паролю~~ → пересмотрено 05:10 (вход по e-mail); серверные сессии в cookie HttpOnly | Безопаснее JWT в localStorage | О5 |
| 2026-10-20 04:35 | Шаблонный `main.py` от PyCharm удаляется на этапе каркаса | Не относится к продукту | — |
| 2026-10-20 04:41 | Каждый пункт «Что мы ожидаем от вас» привязан к файлу и правилу (§1, §16) | Запрос владельца | С1–С7 |
| 2026-10-20 04:41 | Промпты владельца — дословно в `docs/prompts.md` | ТЗ просит промпты | С3 |
| 2026-10-20 04:45 | Экспорт сессии — штатный jsonl Claude Code, e-mail вырезается `tools/export_agent_session.py`; выгрузка ждёт согласия владельца; в git не попадает | В экспорте служебные данные среды | С3 |
| 2026-10-20 04:45 | Коммит после каждого этапа, история не переписывается | Постепенная работа видна | С4 |
| 2026-10-20 04:45 | `.idea/` исключена из git | Личные настройки IDE | — |
| 2026-10-20 04:56 | Владелец подтвердил: один контейнер app с SPA внутри; организатор не участвует; несколько идей на сотрудника; саморегистрация + организатор из env; только локальный запуск | Ответ «Все правильно» на 5 вопросов | О1, О5, О9 |
| 2026-10-20 04:57 | Архитектура разбирается тремя субагентами в три раунда | Запрос владельца | О6 |
| 2026-10-20 05:10 | Р1: SPA внутри контейнера `app`, отдельный nginx-контейнер отклонён | Инвариант одного контейнера | О1 |
| 2026-10-20 05:10 | Р2: модульный монолит, слои проверяются import-linter | Правила без I/O тестируемы; границы проверяемы | О13 |
| 2026-10-20 05:10 | Р4: время — `Clock` приложения, читается после блокировки и заново при повторе | `now()` БД — время начала транзакции; тестируемость | П1, П2 |
| 2026-10-20 05:10 | Р6: `FOR SHARE` конкурса на записи, `FOR UPDATE` на финализации; порядок contest → idea → vote | Голос на границе попадает в итог; нет дедлоков | П2, Ф4 |
| 2026-10-20 05:10 | Р7: `ideas.id` = UUIDv4, остальные PK bigint, порядок в голосовании `ORDER BY id` | Последовательный id выдаёт автора | П4 |
| 2026-10-20 05:10 | Р8: WebSocket + внутрипроцессная шина, только сигналы; LISTEN/NOTIFY и SSE отклонены | Один процесс; лимит 6 соединений у SSE | П7, П11, О11 |
| 2026-10-20 05:10 | В фазе подачи события об идеях получают только автор и организатор | Иначе раскрывается активность и id чужих идей | П3 |
| 2026-10-20 05:10 | Р9: outbox — создание exactly-once, доставка at-least-once (честно) | Exactly-once поверх SMTP невозможен | Ф4, П9 |
| 2026-10-20 05:10 | Вход по e-mail (без отдельного login); Argon2id с параметрами OWASP + семафор 4 | Один идентификатор; защита от OOM при лимите памяти 512 МБ | О5 |
| 2026-10-20 05:10 | Р11: подтверждение e-mail и сброс по почте — вне объёма; allow-list домена; сброс через CLI; Sybil — остаточный риск | Общий Mailpit делает подтверждение бессмысленным | О5 |
| 2026-10-20 05:10 | Сессии: абсолютный срок 7 дней, `revoked_at`, роль не кэшируется | Простота, одна граница для теста | О5 |
| 2026-10-20 05:10 | Создание идеи: `client_request_id` + `request_hash` (с `contest_id`), поиск по ключу до проверки фазы | Повтор после таймаута на дедлайне не должен давать 409 | П2 |
| 2026-10-20 05:10 | Правка идеи: блокировки → совпадение полей → фаза → `version` → UPDATE | Раунд 3: оптимистичный UPDATE пропускал правку после дедлайна | Ф2, П2 |
| 2026-10-20 05:10 | Порядок проверок: 401 → 404 → 403 → 409 | Иначе ответ раскрывает существование идеи | П3, П4 |
| 2026-10-20 05:10 | Лимиты на запись (20 на автора, 1000 на конкурс, мягкие), выдача без обрезки | Обрезка выдачи скрыла бы идеи, участвующие в итоге | Ф3 |
| 2026-10-20 05:10 | Р13: дедлайны неизменяемы после создания | Правка ломает «одно напоминание» | П9 |
| 2026-10-20 05:10 | «Не участвовал» — по текущему состоянию; «участники» письма — авторы текущих идей и голосовавшие; организатор до финала видит результаты без авторов | Толкование ТЗ без лишних таблиц; минимум привилегий | П9, Ф4, Ф5 |
| 2026-10-20 05:10 | Р12: инвариант — `container_name` + session advisory lock + подсчёт по label; хостовый lock-файл отклонён | Атомарность даёт демон; lock ловит запуск мимо Docker | §12 |
| 2026-10-20 05:10 | Р14: без отдельных тестовых стеков; pytest на хосте против `ideas_test`; e2e — режим единственного `app` с `ideas_e2e` | Отдельный стек = второй контейнер приложения | О13, §12 |
| 2026-10-20 05:10 | Один `GET /api/health` (readiness); диагностика через `make status` | Три эндпоинта избыточны, details утекал бы | — |
| 2026-10-20 05:10 | `/api` без версии в пути; problem+json, коды lower_snake_case; `X-App-Build` | API и SPA в одном образе | — |
| 2026-10-20 05:10 | Prometheus, оповещения — N/A локально | Нет сервера сбора | — |
| 2026-10-20 05:10 | Неизвестная ревизия схемы → отказ старта с сообщением, без флага обхода | Защита от запуска старого кода на новой схеме | — |
| 2026-10-20 05:20 | Финальная сверка документов агентом Security & Quality: исправлены 12 расхождений (порядок lock → миграции, allow-list SPA в default deny, фильтр получателей напоминаний, состав `make check`/`make test` и др.) | Проверка на противоречия по требованию владельца | О13 |
| 2026-10-20 05:23 | Репозиторий GitHub `JustExpo/IdeasCompetition`; два ранних коммита объединены в `2e305d0` по просьбе владельца до первой отправки | Запрос владельца; отправка через `git bundle`, на Mac нет учётных данных GitHub | С1, С4 |
| 2026-10-20 05:35 | ~~Р2: слои `domain/services/db/api`~~ → backend делится на модули по частям логики (`user, auth, contest, idea, vote, result, reminder, notification, realtime` + `common`), в каждом слои `model/service/exception/controller/dao/handler` (§4.2) | Указание владельца: по пути должно быть видно, к чему относится модель | О13 |
| 2026-10-20 05:35 | Слой `handler` — реакции не на HTTP-запрос (тики планировщика, события шины) и особые случаи перевода исключений; общий перевод `AppError` → problem+json — один, в `core/http_errors.py` | Название слоя дал владелец без расшифровки; так у слоя одна ясная обязанность и нет дублирования перевода ошибок в 9 модулях | О13 |
| 2026-10-20 05:35 | Инфраструктура без бизнес-логики (config, clock, logging, db, scheduler) — пакет `app/core/`, модули его используют, он модули — нет | Иначе модули дублировали бы инфраструктуру или зависели друг от друга | О13 |
| 2026-10-20 05:40 | Доменные модели — `frozen dataclass(slots=True)` без фреймворков; время — аргумент `now`; naive `datetime` отклоняется в конструкторе | Неизменяемость и проверка инвариантов при создании; модели тестируются без БД | П1, П2 |
| 2026-10-20 05:40 | Исключение несёт `code` и HTTP `status` как атрибуты класса; модели бросают исключения своего модуля | Один общий перевод в problem+json; код ошибки виден рядом с местом, где она возникает | §8 |
| 2026-10-20 05:40 | Нормализация и проверка текста (NFC, обрезка, запрет управляющих и невидимых символов) — `common/model/text.py`, общая для темы конкурса и идеи | Найдено самопроверкой: тема конкурса не проверялась, а идея проверялась | О12 |
| 2026-10-20 05:40 | Персональные данные (e-mail, имя, адрес письма, тексты), автор идеи и тексты идей скрыты из `repr` моделей | Найдено самопроверкой: `repr` dataclass попал бы в логи и раскрыл автора в фазе голосования | П3, П4, §13 |
| 2026-10-20 05:40 | Ранжирование: голоса ↓, `submitted_at` ↑, затем `id` — места уникальны, результат не зависит от порядка входа | П10 и детерминизм итога | Ф4, П10 |
| 2026-10-20 05:40 | Ruff: отключены `RUF001–RUF003` (кириллица как «двусмысленный» символ) | Тексты, комментарии и тесты на русском — это не ошибка | О13 |
| 2026-10-20 05:40 | Самопроверка уровня Senior для каждого кода (§6.5), пункт 12 DoD, отчёты в `docs/code-review/` | Требование владельца | О13, С3 |
| 2026-10-20 05:38 | Изменения попадают в `main` только через MR, который мержит владелец (§16 п. 8). Коммит `e4e41c9` успел попасть в `main` до этого правила; решение об откате — за владельцем | Требование владельца | С4 |
| 2026-10-20 06:02 | План разработки — `Documents/Конкурс идей/` (README, TODO, specs/IC-001…IC-031): 31 задача в 8 этапах, MVP — IC-001…IC-019; TODO.md — единственный источник статусов | Запрос владельца (промпт 13); укрупнено по просьбе владельца 05:53 с 51 и 62 задач агентов | С3, С4 |
| 2026-10-20 06:02 | Предложено (ждёт согласования): MVP включает правку идей и экран организатора с опросом; финализация, письма, напоминания и WebSocket — после MVP | Оба агента сошлись в раунде 2: Ф2 и Ф5 прямо требуются ТЗ, результаты открываются по времени без финализации | Ф2, Ф5, П8 |
| 2026-10-20 06:09 | Владелец утвердил архитектуру этапа 2 и границу MVP (IC-001…IC-019) | Ответ на вопрос 1 плана | все |
| 2026-10-20 06:09 | Зелёный CI обязателен до мержа MR; коммит доменных моделей остаётся в `main` | Ответ на вопрос 2 | С4, О13 |
| 2026-10-20 06:09 | На Mac владельца есть Docker Desktop; приложение разворачивается в Docker одной командой, владелец проверяет `make up` | Ответ на вопрос 3 | О8, О9 |
| 2026-10-20 06:09 | Итоговые письма: победителю «Вы победили», авторам остальных идей «Ваша идея не прошла» | Ответ на вопрос 4 | Ф4 |
| 2026-10-20 06:09 | Срок сдачи — суббота 2026-10-24 | Ответ на вопрос 5 | С4 |
| 2026-10-20 06:11 | Участнику, который только голосовал, — письмо с итогами конкурса (тема и победившая идея) | Ответ владельца | Ф4 |
| 2026-10-20 06:11 | Объём — рабочий прототип по ТЗ: бэкап и восстановление, команды оператора (`reset-password`, `revoke-sessions`, `status`), очистка данных и демо-данные не делаются (IC-028, IC-029 отменены); `check_singleton.sh` остаётся в IC-030. Пункты §7.5, §11.3 и runbook о бэкапе и CLI — план, не реализуются | Ответ владельца | О12 |
| 2026-10-20 06:12 | Каждая задача начинается только по явному согласию владельца (§16 п. 9) | Требование владельца | С4 |
| 2026-10-20 06:14 | Один коммит на MR, перезапись только ветки MR (§16 п. 5) | Требование владельца «Делай squash коммитов в MR» | С4 |
| 2026-10-20 17:30 | Задачи идут по одной: следующая — после мержа MR предыдущей и слова владельца | Выбор владельца на карточке | С4 |
| 2026-10-20 17:35 | IC-001: устаревшие пути (`services.*`, `domain.*`, `app/security`, `compute_phase`, `FakeClock`) заменены модульными; тестовые часы везде — `FrozenClock` | После перехода на модули документ противоречил коду | О13 |
| 2026-10-20 17:35 | IC-001: граф §4.2 — `reminder → idea, vote`; список идей всех фаз отдаёт `vote.service` (маршрут в `vote.controller`), обратного ребра `idea → vote` нет; аудиторию события считает публикующий модуль, `realtime` только рассылает | Иначе граф имел бы циклы или `realtime` знал бы про фазы и авторов | П3, П4, П7, П11 |
| 2026-10-20 17:35 | IC-001: порядок дедлайнов — отдельная ошибка `DeadlinesOrderError` (`deadlines_order`), `invalid_contest` остаётся для темы и описания; код меняется в IC-010 | Контракт §8.2 обещал `deadlines_order`, код отдавал `invalid_contest` | Ф1 |
| 2026-10-20 17:35 | IC-001: событие `phase_changed` не вводится; клиент перечитывает данные по `server_time` в момент дедлайна; тип удаляется из кода в IC-024 | Фаза меняется по времени, публиковать событие некому | П1, П8 |
| 2026-10-20 17:35 | IC-001: запуск — python-лаунчер `app/launcher.py` (lock → миграции → uvicorn в одном процессе) вместо shell-entrypoint | Session advisory lock должен жить всё время работы сервера; shell-скрипт его не удержит | §12 |
| 2026-10-20 17:35 | IC-001: отклонение от Р14 — агент гоняет integration-тесты на локальном PostgreSQL 16 своего контейнера (Docker там нет), Docker-часть проверяет CI | Иначе агент не может проверить код до MR | О13 |
| 2026-10-20 18:10 | IC-002: зависимости рантайма — `fastapi`, `pydantic`, `pydantic-settings`, `uvicorn[standard]` (MIT/BSD-3), `sqlalchemy[asyncio]`, `asyncpg`, `alembic` (MIT/Apache-2.0/MIT), `argon2-cffi` (MIT), `email-validator` (Unlicense), `limits` (MIT), `aiosmtplib` (MIT), `structlog` (MIT/Apache-2.0) | Ровно стек §5; без любого из них не закрывается требование ТЗ (API, БД, пароли, rate limit, почта, логи); лицензии разрешают использование; `pip-audit` — без известных уязвимостей | О2, О4, О5, О10 |
| 2026-10-20 18:10 | IC-002: зависимости разработки — `pytest`, `pytest-asyncio` (Apache-2.0), `pytest-cov`, `pytest-randomly`, `hypothesis` (MPL-2.0), `httpx` (BSD-3), `ruff`, `mypy`, `import-linter` (BSD-2), `pip-audit` (Apache-2.0) | §10 и §6.1; в образ приложения не попадают | О13 |
| 2026-10-20 18:10 | IC-002: `ruff` banned-api запрещает `datetime.now/utcnow/today`, `date.today`, `time.time`, `time.sleep`; в `tests/` дополнительно `asyncio.sleep` (отдельный `tests/ruff.toml`); исключение для `app/core/clock.py` задаётся в IC-003 | §6.2, §10.3, Р4 | П1, П2 |
| 2026-10-20 18:10 | IC-002: tests/unit автоматически получают маркер `unit` (хук в `tests/unit/conftest.py`); `isort known-first-party = [app, tests]` | Единая сортировка импортов из `backend/` и `tests/ruff.toml`; `pytest -m unit` не требует ручных меток | О13 |
| 2026-10-20 18:10 | IC-002: CI — два job (`backend`, `security`), actions по мажорным тегам (`checkout@v4`, `setup-uv@v6`, `gitleaks-action@v2`), права `contents: read` | Зелёный CI обязателен до мержа (06:09); минимум прав | О13 |
| 2026-10-20 18:50 | IC-003: зависимость `tzdata` (Apache-2.0, только данные часовых поясов) | `DISPLAY_TZ` проверяется через `zoneinfo`; в slim-образах и на Windows базы поясов может не быть, без неё валидный пояс отклонялся бы | О12, Ф4 |
| 2026-10-20 18:50 | IC-003: все ошибки настроек печатаются списком `ИМЯ: причина` без значений и завершают процесс кодом 2; пустая переменная — ошибка, а не «нет значения»; пароль-заглушка из `.env.example` — константа `EXAMPLE_ORGANIZER_PASSWORD`, тест сверяет её с файлом | §11.2; значения секретов не попадают в лог запуска (§9.4) | О12 |
| 2026-10-20 18:50 | IC-003: `app.core` может импортировать `app.common` (ошибки и типы), но не предметные модули; `model`/`exception` не импортируют `app.core` — контракты import-linter (17 штук) | Для `core/http_errors.py` нужен `AppError`; чистые модели не знают про инфраструктуру | О13 |
| 2026-10-20 18:50 | IC-003: маскирование логов стоит в цепочке structlog до форматтера (и для стандартного `logging`): e-mail → `a***@домен`, поля `password`, `token`, `secret`, `cookie`, `authorization`, `sid`, `body`, `title`, `description` → `[REDACTED]`, текст исключений тоже маскируется | Одна точка защиты от утечки ПДн и текстов идей, `caplog` её видит | П3, П4, §13 |
| 2026-10-20 18:50 | IC-003: `ruff`: `TID251` отключён только для `app/core/clock.py`; в `tests/**` отключены `S105`/`S106` (фиктивные пароли в тестах) | Одно место чтения времени (Р4); тестовые значения не секреты | О13 |
| 2026-10-20 19:10 | IC-004: политика маршрута — зависимость `require(Policy.PUBLIC\|AUTHENTICATED\|EMPLOYEE\|ORGANIZER\|E2E_ONLY)`; `create_app` падает с `RoutePolicyError` и списком путей, если у маршрута `/api` (HTTP или WebSocket) нет политики или публичный маршрут не в allow-list `PUBLIC_API_PATHS`; до появления сессий (IC-007) любая политика кроме `PUBLIC` отвечает 401 | Default deny (§9.2): забытая проверка личности закрывает маршрут, а не открывает | П3, П4 |
| 2026-10-20 19:10 | IC-004: тело ошибки problem+json не содержит присланных значений: для 422 — только путь к полю и тип ошибки pydantic; неверный JSON — 400 `invalid_json`; 500 — `internal_error` без стека и SQL (причина в логе, замаскированная) | Значение поля может быть паролем или текстом идеи; сообщение pydantic иногда цитирует значение | §8.1, §13 |
| 2026-10-20 19:10 | IC-004: прослойки — чистый ASGI в порядке контекст запроса → `Origin` → тело; лимит 64 КБ считается и по `Content-Length`, и по фактическим байтам (FastAPI превращает сбой чтения тела в 400, поэтому ответ подменяется на 413); `Origin` обязателен для POST/PUT/PATCH/DELETE | `BaseHTTPMiddleware` буферизует тело; `Content-Length` можно не указать или солгать; SameSite=Lax от CSRF не защищает полностью | §8.1, §9.3 |
| 2026-10-20 19:10 | IC-004: `/docs`, `/redoc`, `/openapi.json` отключены, контракт берётся из `app.openapi()` (экспорт — IC-024/IC-031); временный `/api/health` без БД лежит в `core/health.py` и заменяется в IC-005 | Swagger UI тянет скрипты с CDN, что противоречит CSP; маршрут, объявленный сервером без политики, нарушал бы default deny | §8.1, §9.2 |
| 2026-10-20 19:35 | IC-005: `Database.run_in_transaction(work)` — метод класса `core/db.py`; при дедлоке (`40P01`) и сбое сериализации (`40001`) откатывает транзакцию и вызывает `work` заново целиком, до 3 повторов (4 попытки) с джиттером; поэтому `work` сам читает `Clock` после блокировок (Р4), а события уходят после возврата | Повтор «снизу» без перезапуска сценария дал бы устаревшее `now` и устаревшие проверки | П2, Р6 |
| 2026-10-20 19:35 | IC-005: недоступной БД считаются потеря связи, отказ в подключении, остановка сервера, таймаут пула, `lock_timeout` и `statement_timeout`; в таких случаях `run_in_transaction` бросает `ServiceUnavailableError` (503 `service_unavailable`, `Retry-After: 5`, поле `AppError.retry_after`); остальные ошибки драйвера (в т.ч. неверный пароль) проходят как есть и дают 500 | Клиенту стоит повторить запрос при перегрузке, но не при ошибке настройки | §7.3, §8.1 |
| 2026-10-20 19:35 | IC-005: `/api/health` = 200 только если БД отвечает ≤ 1 с и ревизия схемы равна «голове» миграций приложения; обе ревизии пишутся в лог, наружу — только 503 без деталей. Лаунчер (IC-006) использует `Database.ensure_schema_is_current` и `wait_until_available` (60 с) | Неизвестная и отстающая ревизии одинаково опасны; health не должен раскрывать устройство БД | §7.4, §9.3 |
| 2026-10-20 19:35 | IC-005: Alembic — `backend/alembic.ini`, `migrations/env.py` читает `DATABASE_URL` из окружения (без остальных настроек), одна транзакция на миграцию, `lock_timeout=5s`, модели берутся из `app/<модуль>/dao` по мере их появления; базовая ревизия `0001` пуста; `Base` и соглашение об именах ограничений — в `core/db.py` | Миграции запускаются в CI и контейнере без полного набора настроек; имена ограничений нужны dao для перевода `IntegrityError` | §7.4, Р5 |
| 2026-10-20 19:35 | IC-005: integration-тесты — `TEST_DATABASE_URL` (по умолчанию `127.0.0.1:5433/ideas_test`), отказ при имени БД без суффикса `_test`, в начале прогона схема пересоздаётся и мигрируется до `head`; обычные тесты — транзакция с откатом (savepoint), тесты с реальным commit — маркер `commits` и TRUNCATE; в CI отдельный job с `postgres:16` и циклом `upgrade → check → downgrade -1 → upgrade` | Тесты стирают схему целиком: защита от запуска на рабочей БД; повтор транзакции в savepoint даёт ложнозелёный результат | §10.1, О13 |
| 2026-10-20 23:35 | IC-006: лаунчер — `app/core/launcher.py`, блокировка — `app/core/singleton.py` (пути в CLAUDE.md §4.1/§7.4 уточнены, прежнее `app/launcher.py` — предложение IC-001); порядок: ожидание БД ≤ 60 с → блокировка (повторы ≤ 30 с, при отказе в сообщении pid, адрес и время старта держателя из `pg_stat_activity`, без текстов запросов) → `alembic upgrade head` в потоке → проверка ревизии → uvicorn; код выхода 1 при отказе | Shell-скрипт не удержит session lock; сообщение оператору должно говорить, кого остановить | §12 |
| 2026-10-20 23:35 | IC-006: монитор блокировки раз в 10 с — потеря соединения → попытка взять заново (короткий обрыв БД), занята другим → сервер останавливается с кодом 1; `/api/health` = 503 при потере блокировки и во время остановки (флаг `draining` ставится в обработчике SIGTERM до остановки uvicorn) | Два сервера на одной БД недопустимы; балансировщик/healthcheck должны перестать слать запросы до закрытия | §11.4, §12 |
| 2026-10-20 23:35 | IC-006: `DrainingServer.capture_signals` не пересылает пойманный сигнал себе после остановки (штатный uvicorn ≥ 0.29 это делает, и процесс умирал по SIGTERM, минуя `finally` с освобождением блокировки и `dispose`) | Корректное завершение по §11.4 | §11.4 |
| 2026-10-20 23:35 | IC-006: Dockerfile — `python:3.12-slim`, `uv==0.11.32` через pip, зависимости по `uv.lock` без dev, непривилегированный пользователь 10001; стадия node не добавлена (IC-015). compose: `container_name`, label, порты на 127.0.0.1 (`8000`, `8025`, БД `5433`), `init`, `stop_grace_period 20s`, лимиты, healthcheck через python; Mailpit `axllent/mailpit:v1.21`; пароль БД — `POSTGRES_PASSWORD` в `.env` (должен совпадать с `DATABASE_URL`) | §11–§12 | О8, О9, О10 |
| 2026-10-20 23:35 | IC-006: `scripts/up.sh` — проверка Docker и порта 8000, `.env` из примера, preflight по label (чужие контейнеры не удаляются), `up -d --build --wait`, постпроверка «ровно один»; предупреждение о ближайшем дедлайне (<1 ч) не делается до появления таблицы конкурсов; `make status`, `backup`, `restore*`, `destroy`, `e2e` не создаются (отменены или в IC-030); `make cli` ждёт `app.cli` из IC-007 | Объём прототипа (06:11) | §12 |
| 2026-10-20 23:35 | IC-006: зависимостей не добавлено; `asyncpg` напрямую используется в `core/singleton.py` (уже в стеке), для mypy задан override `ignore_missing_imports` (у пакета нет типов); в CI добавлен job `docker` (make up → health 200 → повторный `make up` с тем же ID → ровно один контейнер → `make down` сохраняет volume) | У агента нет демона Docker; проверка — в CI и у владельца | О13 |
| 2026-10-20 23:59 | IC-007: сессия — токен `secrets.token_urlsafe(32)`, в БД SHA-256, срок 7 дней без продления, валидна при `revoked_at IS NULL AND now < expires_at` (на `expires_at` уже недействительна); cookie `sid`, в prod `__Host-sid` + `Secure`, в dev/e2e без `Secure` (http); каждый запрос — 2 SQL (сессия, пользователь), `is_active` и роль не кэшируются | Изменение прав и деактивация действуют со следующего запроса | О5 |
| 2026-10-20 23:59 | IC-007: Argon2id (m=19456 КиБ, t=2, p=1) считается в `asyncio.to_thread` под семафором 4 и вне транзакции БД; неизвестный e-mail проверяется по фиктивному хэшу; пароль длиннее 128 символов отклоняется без хэширования (известная разница по времени); устаревший хэш обновляется при входе; хэширование живёт в `auth.service`, `user.service` знает только готовый хэш | `user` стоит ниже `auth` и не может его импортировать; семафор защищает память контейнера 512 МБ | О5 |
| 2026-10-20 23:59 | IC-007: константы и нормализация пароля (10–128, NFKC) — `common/model/password.py`; `ForbiddenError` и `OrganizerCannotParticipateError` — `common/exception` | Используются и `core.access`, и `config`, и модулями; `core` не может импортировать предметные модули | П4 |
| 2026-10-20 23:59 | IC-007: `RequirePolicy` получает личность через `app.state.actor_resolver` (его задаёт `create_app`), поэтому `core` не импортирует `auth`; нет сессии → 401 `not_authenticated`, ORGANIZER чужой ролью → 403 `forbidden`, EMPLOYEE организатором → 403 `organizer_cannot_participate`; `E2E_ONLY` до задачи e2e отвечает 401 | Default deny без обратной зависимости core → предметный модуль | П3, П4 |
| 2026-10-20 23:59 | IC-007: организатор создаётся в lifespan при `bootstrap_organizer=True` (передаёт лаунчер) и командой `python -m app.cli create-organizer`; повтор ничего не меняет, e-mail сотрудника не повышается (`EmailTakenError`), сбой прерывает старт | Идемпотентность и минимум привилегий | О5 |
| 2026-10-20 23:59 | IC-007: контракты import-linter «запрет импорта чужих dao/controller/handler» проверяют только прямые импорты (`allow_indirect_imports = True`) | Иначе цепочка controller → service → dao и service → чужой service → его dao ломала бы правило, хотя запрещены лишь прямые зависимости (§4.2) | О13 |
| 2026-10-20 23:59 | IC-007: зависимостей не добавлено; миграция `0002` — таблицы `users` и `sessions` (expand), ограничения именованы для перевода `IntegrityError` | Стек §5 | О4 |

## 18. Хронология этапов

| Этап | Начало (UTC) | Конец (UTC) | Коммит | Итог |
|------|--------------|-------------|--------|------|
| 0. Изучение ТЗ, подключение папки | 2026-10-20 04:24 | 2026-10-20 04:30 | — | ТЗ разобрано, папка подключена |
| 1. План и требования к отчёту | 2026-10-20 04:30 | 2026-10-20 04:45 | `2e305d0` | CLAUDE.md, README.md, docs/prompts.md, скрипт экспорта |
| 2. Архитектура и правила разработки | 2026-10-20 04:55 | 2026-10-20 05:20 | `2e305d0` (вместе с этапом 1, объединены по просьбе владельца) | CLAUDE.md, docs/architecture-review.md, docs/edge-cases.md, docs/runbook.md, отчёты агентов |
| 4а. Структура пакетов и доменные модели | 2026-10-20 05:29 | 2026-10-20 05:45 | `Созданы базовые доменные модели и структура пакетов backend` | `backend/app/*` (9 модулей + common), `backend/tests/unit`, `backend/pyproject.toml`, §4 и §6.5 CLAUDE.md, `docs/code-review/` |
| План разработки (to-do-list и спецификации) | 2026-10-20 05:47 | 2026-10-20 06:02 | ветка `docs/development-plan`, MR | `Documents/Конкурс идей/` |
| IC-001. CLAUDE.md в соответствии с модулями | 2026-10-20 17:28 | 2026-10-20 17:40 | ветка `feature/IC-001-claude-md`, MR | CLAUDE.md §1, §4.2, §7, §8.2, §10, §16, §17; `docs/edge-cases.md`, `docs/runbook.md` |
| IC-002. Зависимости, import-linter, CI | 2026-10-20 17:34 | 2026-10-20 18:15 | ветка `feature/IC-002-ci`, MR | `backend/pyproject.toml`, `uv.lock`, `.python-version`, `.importlinter`, `tests/ruff.toml`, `.github/workflows/ci.yml` |
| IC-003. Конфигурация, часы, логирование | 2026-10-20 18:44 | 2026-10-20 19:10 | ветка `feature/IC-003-core`, MR #5 | `backend/app/core/{config,clock,logging}.py`, `tests/fakes.py`, `tests/unit/core/`, `.env.example` |
| IC-004. Приложение FastAPI, problem+json, доступ по умолчанию | 2026-10-20 18:55 | 2026-10-20 19:15 | ветка `feature/IC-004-app`, MR #6 | `backend/app/main.py`, `core/{access,http_errors,middleware,health}.py`, `common/exception`, `tests/unit/core/test_app_http.py` |
| IC-005. PostgreSQL, транзакции, миграции Alembic | 2026-10-20 19:02 | 2026-10-20 19:40 | ветка `feature/IC-005-db`, MR #7 | `backend/app/core/db.py`, `alembic.ini`, `migrations/`, `tests/integration/`, job `integration` в CI |
| IC-006. Docker Compose, Makefile, лаунчер | 2026-10-20 23:19 | 2026-10-20 23:45 | ветка `feature/IC-006-docker`, MR | `Dockerfile`, `compose.yaml`, `Makefile`, `scripts/up.sh`, `backend/app/core/{launcher,singleton}.py`, job `docker` в CI |
| IC-007. Вход, выход, сессии, организатор | 2026-10-20 23:41 | 2026-10-20 23:59 | ветка `feature/IC-007-auth`, MR | `backend/app/{user,auth}/*`, `core/access.py`, `app/cli.py`, миграция `0002`, `tests/integration/test_auth_api.py` |
