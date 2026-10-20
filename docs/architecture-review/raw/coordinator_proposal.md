# Предварительные решения координатора по разногласиям (раунд 3)

К1. Подтверждение e-mail и сброс пароля по почте — НЕ в объёме. Allow-list домена (`ALLOWED_EMAIL_DOMAINS`), сброс через CLI `exec`. Sybil — остаточный риск в README.
К2. `ideas.id` = UUIDv4 (`gen_random_uuid()`), прочие PK bigint. Порядок в голосовании `ORDER BY id`. HMAC нет.
К3. Создание идеи: `client_request_id` (UUID) в ТЕЛЕ + колонка `request_hash`; порядок: поиск по (author_id, client_request_id) → найдено: hash совпал → 200 с идеей, иначе 422 `idempotency_key_reused` → видимость/роль → FOR SHARE конкурса → now → фаза → INSERT ON CONFLICT DO NOTHING RETURNING (пусто → SELECT).
К4. Правка идеи: поле `version`, `UPDATE ... SET version=version+1 WHERE id AND author AND version=:v`; 0 строк → SELECT FOR UPDATE и выбор 404 / 409 submission_closed / 409 stale_version; если поля равны присланным → 200.
К5. Префикс `/api` без `/v1`; только аддитивные изменения контракта + заголовок `X-App-Build`. problem+json, коды lower_snake_case. Повтор голоса → 204.
К6. Health: один `GET /api/health` (readiness: БД, singleton-lock, схема); диагностика — `make status` (CLI через exec). Нет /health/details.
К7. Push: WebSocket (аргумент лимита 6 соединений HTTP/1.1 у SSE) + обязательная проверка Origin (`ALLOWED_ORIGINS`, `:5173` только в dev). Сигналы без данных. В фазе подачи события об идеях — только автору и организатору; `idea_deleted` всем — только в голосовании. In-process шина, без LISTEN/NOTIFY. Отзыв сессии: logout через шину; CLI-отзыв — перепроверка сессии WS раз в 60 с.
К8. Единственный контейнер: `container_name` + session advisory lock в БД на выделенном соединении (не из пула) + подсчёт по label как проверка. Без mkdir-lock. Планировщик — `pg_try_advisory_xact_lock` на тик.
К9. Тесты: pytest на хосте через `uv run` против БД `ideas_test` в существующем контейнере `db` (порт 127.0.0.1:5433); conftest отказывается работать с БД без суффикса `_test`. CI — service-контейнер postgres. Изоляция savepoint, тесты с commit — маркер `commits` + TRUNCATE.
К10. E2E: `compose.e2e.yaml` поверх основного (тот же container_name), `APP_ENV=e2e`, БД `ideas_e2e`; тестовые часы только при `_e2e` и только вперёд; `trap 'make up'`; плашка E2E MODE в UI; per-IP rate limit в e2e выключен.
К11. «Не участвовал» = по текущему состоянию (нет текущих идей / текущих голосов). Без таблицы participations.
К12. Лимиты на запись: ≤20 идей на автора, ≤1000 на конкурс (409 contest_full); выдача списка полная.
К13. Дедлайны неизменяемы после создания.
К14. Организатор до финала видит результаты без авторов. «Участники» финального письма = авторы текущих идей + проголосовавшие. Нулевые голоса у всех → победитель самая ранняя идея по правилу ничьей; идей нет → победителя нет.
К15. Argon2id с параметрами OWASP (m=19 МиБ, t=2, p=1) + семафор 4; rate limit входа 5/15 мин на (email, IP) и регистрации 5/ч на IP, in-memory (`limits`).
К16. Сессии: только абсолютный срок 7 дней, `revoked_at`, роль не кэшируется.
К17. Отказ старта старой версии на новой схеме — N/A локально, записан в план прод-выкладки.
К18. Время: `Clock` приложения, `now` читается ПОСЛЕ блокировки и заново при каждом повторе транзакции; `now()` БД только в технических created_at.
