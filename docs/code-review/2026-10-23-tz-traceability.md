# Сверка с ТЗ: требование → автоматический тест (IC-031)

Дата: 2026-10-23. Каждая строка CLAUDE.md §1 с поведением указывает тест, который падает, если поведение сломано.
`backend/tests/…` — pytest (unit и integration на PostgreSQL 16), `e2e/tests/…` — Playwright в Chromium против
приложения в режиме e2e (тестовые часы, Mailpit), `frontend/src/…` — Vitest. Имена функций сверены `grep`-ом с кодом.

## Функциональные требования

| № | Требование | Тест |
|---|---|---|
| Ф1 | Конкурс: тема и два дедлайна | `integration/contests/test_contests_api.py::test_organizer_creates_contest_and_sees_card`, `::test_voting_must_close_strictly_after_submission`, `::test_deadlines_one_microsecond_apart_are_allowed`, `::test_regression_deadline_offset_is_normalized_to_utc`; unit `test_contest_model.py::test_schedule_requires_voting_after_submission` |
| Ф2 | Подача и правка до закрытия | `test_ideas_submit_api.py::test_employee_submits_idea`, `::test_submission_closes_exactly_at_the_deadline`; `test_ideas_edit_api.py::test_author_edits_idea_and_version_grows`, `::test_edit_closes_exactly_at_the_submission_deadline`, `::test_stale_version_is_rejected`; e2e `deadline.spec.ts › правка идеи` |
| Ф3 | Голосование: идеи без авторов, один голос на идею | `test_ideas_list_api.py::test_voting_shows_everything_without_authors`; `test_voting_api.py::test_vote_is_idempotent_and_shown_as_my_vote` |
| Ф4 | Финал: авторы раскрыты, письма победителю и всем | `test_ideas_list_api.py::test_finished_reveals_authors_to_everyone`; `test_finalization.py::test_finalization_fixes_winner_and_queues_one_email_per_participant`, `::test_author_of_several_ideas_gets_single_email`; `test_email_delivery.py::test_successful_delivery_marks_sent`; e2e `full-cycle.spec.ts` (три разных письма в Mailpit) |
| Ф5 | Экран организатора: идеи, проголосовавшие, результаты | `test_results_api.py::test_full_contest_cycle`; e2e `full-cycle.spec.ts` (числа «Идей подано» / «Проголосовало»), `realtime.spec.ts › П7` |

## Ожидаемое поведение

| № | Требование | Тест |
|---|---|---|
| П1 | Раунды закрываются сами по времени | unit `test_contest_model.py::test_phase_boundaries`; `test_ideas_list_api.py::test_list_flips_at_exact_deadlines`; `test_finalization.py::test_not_finalized_before_voting_deadline`; e2e `full-cycle.spec.ts` (часы переведены за дедлайны) |
| П2 | После закрытия идея и голос не принимаются, даже при открытой странице | `test_ideas_submit_api.py::test_submission_closes_exactly_at_the_deadline`, `::test_retry_after_the_deadline_returns_the_accepted_idea`; `test_voting_api.py::test_vote_boundaries`; `test_finalization.py::test_vote_accepted_before_deadline_is_counted_in_final_result`; e2e `deadline.spec.ts` (подача, правка, голос); Vitest `app/contestPage.test.tsx` («voting_closed…», «submission_closed…») |
| П3 | В подаче чужие идеи не видны | `test_ideas_list_api.py::test_submission_shows_only_own_ideas`; `test_realtime.py::test_submission_events_reach_only_author_and_organizer`; e2e `full-cycle.spec.ts` (Боб не видит идею Алисы) |
| П4 | В голосовании без авторов; за свою нельзя | `test_ideas_list_api.py::test_voting_shows_everything_without_authors`; `test_voting_api.py::test_own_idea_vote_is_forbidden`; `test_log_hygiene.py` (авторство не попадает в лог); e2e `full-cycle.spec.ts` |
| П5 | Один голос при любом числе вкладок | `test_voting_api.py::test_parallel_votes_create_single_row`; e2e `realtime.spec.ts › П5` (две вкладки + три параллельных PUT) |
| П6 | Голос можно отозвать до закрытия | `test_voting_api.py::test_withdraw_is_idempotent`; `test_results_api.py::test_counts_follow_withdrawn_votes_and_deleted_ideas`; Vitest «Отозвать голос» |
| П7 | Организатор видит изменения без обновления страницы | `test_realtime.py::test_vote_signals_organizer_and_voters_other_tab_only`; Vitest `app/realtime.test.tsx`; e2e `realtime.spec.ts › П7` (≤ 2 с) |
| П8 | Остальные видят результаты только после финала | `test_results_api.py::test_full_contest_cycle` (сотрудник получает 403 до финала, итоги — после дедлайна); unit `test_policies.py` (таблица `can_view_results`); e2e `full-cycle.spec.ts` |
| П9 | За сутки одно напоминание не участвовавшим | `test_reminders.py::test_submission_reminder_goes_to_employees_without_ideas`, `::test_repeated_and_parallel_ticks_send_one_reminder_per_person`, `::test_window_boundaries_for_submission_round`; e2e `reminders.spec.ts` |
| П10 | Ничья — раньше поданная; правило видно заранее | unit `test_result_ranking.py::test_tie_goes_to_earlier_submission` и свойство «порядок входа не важен» (Hypothesis); `test_results_api.py::test_tie_goes_to_earlier_submission`; `test_finalization.py::test_tie_is_resolved_by_earlier_submission_and_mentioned_in_email`; e2e `full-cycle.spec.ts` (строка «Правило ничьей» с фазы подачи) |
| П11 | Удалённая идея исчезает у всех вместе с голосами | `test_voting_api.py::test_delete_idea_removes_votes_and_blocks_after_finish`, `::test_delete_races_with_vote_without_orphans`; `test_realtime.py::test_deleting_in_voting_reaches_everyone_and_organizer_recounts`; e2e `realtime.spec.ts › П11` (≤ 2 с) |

## Общие требования и отчётность

| № | Что | Чем доказано |
|---|---|---|
| О1–О4 | Клиент-сервер, Python/FastAPI, React, PostgreSQL | структура репозитория; job `docker` в CI (образ собирается, SPA отдаётся контейнером) |
| О8–О9 | Развёртывание и быстрый запуск | `make up` (job `docker`); README «Запуск»; на Mac владельца ещё не проверено |
| О10 | Почта эмулируется | Mailpit в `compose.yaml`; e2e читает письма через его API |
| О11 | Два клиента одновременно | e2e `realtime.spec.ts` (два контекста / две вкладки) |
| О13 | Доказуемость | CI: backend, integration (+покрытие ≥ 95 %), frontend, contract, docker (+`check_singleton.sh`), e2e, security |
| Р12 | Один контейнер приложения | `scripts/check_singleton.sh` в job `docker`; `test_singleton_launcher.py` |
| §13 | Нет секретов, текстов идей и связки автор ↔ идея в логах | `test_log_hygiene.py` (включая проверку, что детектор ловит намеренную утечку e-mail) |

## Что не доказано автоматически

- `make up`, `make e2e`, `check_singleton.sh` и CI-job `docker`/`e2e` в окружении агента не запускались: там нет демона Docker.
  Проверка — CI на GitHub и владелец на Mac. Содержимое e2e-сценариев при этом прогнано локально тем же Playwright
  против настоящего приложения (`APP_ENV=e2e`), PostgreSQL 16 и настоящего Mailpit.
- Реальный почтовый провайдер не проверялся (только Mailpit и поддельный SMTP-сервер по настоящему протоколу).
