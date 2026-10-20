# Самопроверка: структура пакетов и доменные модели backend

Дата: 2026-10-20, 05:40 UTC. Правило — `CLAUDE.md` §6.5. Ревьюер — агент (Claude Code) в роли Senior-разработчика.
Объект: `backend/app/**` (9 модулей + `common`), `backend/tests/unit/**`, `backend/pyproject.toml`.

## Что запускалось

Облачный контейнер агента, Python 3.13 (целевая версия 3.12 задана в `ruff target-version` и `mypy python_version`):

| Команда (из `backend/`) | Итог |
|---|---|
| `python3 -m pytest -q` | 47 passed |
| `ruff check .` (наборы §6.1) | All checks passed |
| `ruff format --check .` | 92 files already formatted |
| `python3 -m mypy app tests` (strict) | Success: no issues found in 92 source files |

На Mac владельца не запускалось: там нет Python 3.12 и `uv`; это проверяется на этапе каркаса.

## Найдено и исправлено

| # | Ось | Проблема | Исправление |
|---|---|---|---|
| 1 | Безопасность | `repr` dataclass `User` и `OutboxEmail` содержал e-mail, имя, тему и текст письма: любой `log.info(user)` писал бы персональные данные в логи (§13) | `field(repr=False)` для e-mail, имени, адреса, темы, текста и `last_error`; тесты `test_user_repr_hides_personal_data`, `test_outbox_email` |
| 2 | Безопасность | `repr` `Idea` и `IdeaScore` содержал `author_id`: связка автор ↔ идея в фазе голосования попала бы в логи (П3, П4) | `author_id` и тексты скрыты из `repr`; тест `test_repr_hides_author_and_text` |
| 3 | Безопасность | Тема и описание конкурса не проверялись на управляющие и невидимые символы (U+202E переворачивает текст), а идея проверялась | Общий модуль `common/model/text.py` (`normalize_text`, `has_forbidden_chars`) для идеи и конкурса; тест `test_contest_rejects_bad_topic` |
| 4 | Структура | Ошибка темы/описания конкурса называлась `InvalidContestScheduleError` — имя врёт о причине | Переименовано в `InvalidContestError` (код `invalid_contest` не изменился) |
| 5 | Корректность | `ContestEvent` можно было создать без адресата (событие конкурса без `contest_id`, отзыв сессии без `user_id`) — хаб не знал бы, кому слать | Инварианты в `__post_init__`; тест `test_event_invariants` |
| 6 | Структура | Нарушение `version` и `updated_at < submitted_at` бросало `InvalidIdeaContentError` («неверный текст идеи») | Бросается общая `DomainValidationError` |
| 7 | Структура | Длинные строки, порядок импортов, «двусмысленная» кириллица (ruff `RUF001–003`) | Исправлено; `RUF001–003` отключены с обоснованием в `pyproject.toml` и §17 |

## Проверено, замечаний нет

- **Архитектура.** `model` и `exception` не импортируют фреймворки, БД и часы; время приходит аргументом `now`. Межмодульные импорты идут только по графу §4.2: `auth.model → user.model`, `reminder.model → contest.model`, все — в `common`. Циклов нет (импорт всех пакетов проходит).
- **Корректность границ.** Фаза на `d−1µs / d / d+1µs` для обоих дедлайнов; дедлайн в другом часовом поясе; naive `datetime` отклоняется; сессия на границе `expires_at`; окно напоминания `[deadline − 24h, deadline)`; длины 200/201 и 10 000/10 001; ничья по голосам и по нулю голосов; детерминизм ранжирования при полной ничьей.
- **Неизменяемость.** Все модели `frozen=True, slots=True`; изменение — только новым объектом из сервиса.

## Осталось осознанно (известные ограничения)

- Длина текста считается в кодовых точках, не в графемах (`docs/edge-cases.md`): эмодзи-последовательность «весит» больше одного символа.
- Модель `Contest` проверяет инварианты, но не нормализует тему: нормализация (`normalize_text`) — обязанность `service` при создании; у идеи для этого есть `IdeaContent.create`.
- Формат e-mail в `User` не проверяется: это задача схемы `controller` (email-validator) и уникального индекса в БД.
- Тест ранжирования на Hypothesis (§10) и конфиг `.importlinter` появятся на этапе каркаса вместе с зависимостями; сейчас в `pyproject.toml` только pytest, ruff, mypy.
- Слои `service/controller/dao/handler` пусты (только описание в `__init__.py`) — по указанию владельца работаем малыми шагами.
