import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContestDetail } from "../api";
import { renderApp } from "../test/render";
import { apiUrl, employee, http, HttpResponse, organizer, problem, server } from "../test/server";

function contest(
  phase: ContestDetail["phase"],
  actions: ContestDetail["allowed_actions"],
): ContestDetail {
  return {
    id: 7,
    topic: "Как улучшить офис",
    description: "Любые идеи",
    created_at: "2026-10-20T10:00:00+00:00",
    // Дедлайны далеко в будущем: таймеры не срабатывают посреди теста.
    submission_deadline: "2099-01-01T12:00:00+00:00",
    voting_deadline: "2099-01-02T12:00:00+00:00",
    phase,
    server_time: new Date().toISOString(),
    allowed_actions: actions,
    tie_break_rule: "При равенстве голосов побеждает идея, поданная раньше.",
  };
}

const asEmployee = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(employee));
const asOrganizer = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(organizer));
const contestUrl = apiUrl("/api/contests/7");
const ideasUrl = apiUrl("/api/contests/7/ideas");

function own(id: string, title: string, version = 1) {
  return {
    id,
    title,
    description: `Описание: ${title}`,
    version,
    submitted_at: "2026-10-21T09:00:00+00:00",
    updated_at: "2026-10-21T09:00:00+00:00",
  };
}

function votable(id: string, title: string, isMine = false, myVote = false) {
  return { id, title, description: `Описание: ${title}`, is_mine: isMine, my_vote: myVote };
}

/** Уход со вкладки и возвращение: так браузер сообщает react-query о фокусе. */
function returnToTab(): void {
  for (const state of ["hidden", "visible"] as const) {
    Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
    window.dispatchEvent(new Event("visibilitychange"));
  }
}

describe("страница конкурса: приём идей", () => {
  it("показывает карточку, правило ничьей и только свои идеи", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () =>
        HttpResponse.json({ phase: "submission", items: [own("a1", "Кофе-поинт")] }),
      ),
    );
    renderApp("/contests/7");
    expect(await screen.findByRole("heading", { name: "Как улучшить офис" })).toBeInTheDocument();
    expect(screen.getByText(/При равенстве голосов побеждает идея, поданная раньше/)).toBeVisible();
    expect(await screen.findByText("Кофе-поинт")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Новая идея" })).toBeInTheDocument();
  });

  it("двойной клик отправляет одну идею, а после успеха форма очищается и ключ новый", async () => {
    const keys: string[] = [];
    let ideas = [own("a1", "Первая")];
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: ideas })),
      http.post(ideasUrl, async ({ request }) => {
        const body = (await request.json()) as { client_request_id: string; title: string };
        keys.push(body.client_request_id);
        ideas = [...ideas, own("a2", body.title)];
        return HttpResponse.json(own("a2", body.title), { status: 201 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Название"), "Вторая");
    await user.type(screen.getByLabelText("Описание"), "Подробности");
    const button = screen.getByRole("button", { name: "Предложить идею" });
    await user.dblClick(button);

    expect(await screen.findByText("Описание: Вторая")).toBeInTheDocument();
    expect(keys).toHaveLength(1);
    expect(screen.getByLabelText("Название")).toHaveValue("");

    await user.type(screen.getByLabelText("Название"), "Третья");
    await user.type(screen.getByLabelText("Описание"), "Ещё");
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    await waitFor(() => {
      expect(keys).toHaveLength(2);
    });
    expect(keys[1]).not.toBe(keys[0]);
  });

  it("повтор того же текста после ошибки идёт с тем же ключом, правка текста — с новым", async () => {
    const keys: string[] = [];
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: [] })),
      http.post(ideasUrl, async ({ request }) => {
        const body = (await request.json()) as { client_request_id: string };
        keys.push(body.client_request_id);
        return problem({ code: "service_unavailable", status: 503 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Название"), "Идея");
    await user.type(screen.getByLabelText("Описание"), "Текст");
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    await screen.findByText(/Сервис временно недоступен/);
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    await waitFor(() => {
      expect(keys).toHaveLength(2);
    });
    expect(keys[1]).toBe(keys[0]);

    await user.type(screen.getByLabelText("Название"), "!");
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    await waitFor(() => {
      expect(keys).toHaveLength(3);
    });
    expect(keys[2]).not.toBe(keys[0]);
  });

  it("submission_closed: понятный текст, введённый текст остаётся", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: [] })),
      http.post(ideasUrl, () => problem({ code: "submission_closed", status: 409 })),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Название"), "Опоздавшая идея");
    await user.type(screen.getByLabelText("Описание"), "Текст");
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    expect(await screen.findByText("Приём идей закрыт.")).toBeInTheDocument();
    expect(screen.getByLabelText("Название")).toHaveValue("Опоздавшая идея");
  });

  it("не отправляет пустую форму и считает эмодзи кодовыми точками на границе 200/201", async () => {
    let posts = 0;
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: [] })),
      http.post(ideasUrl, () => {
        posts += 1;
        return HttpResponse.json(own("a1", "x"), { status: 201 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Предложить идею" }));
    expect(await screen.findByText("Введите название идеи.")).toBeInTheDocument();
    expect(posts).toBe(0);

    const title = screen.getByLabelText("Название");
    await user.click(title);
    await user.paste("😀".repeat(201));
    await user.type(screen.getByLabelText("Описание"), "Текст");
    expect(screen.getByText("201 из 200")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    expect(await screen.findByText("Название не длиннее 200 символов.")).toBeInTheDocument();
    expect(posts).toBe(0);

    await user.clear(title);
    await user.click(title);
    await user.paste("😀".repeat(200));
    await user.click(screen.getByRole("button", { name: "Предложить идею" }));
    await waitFor(() => {
      expect(posts).toBe(1);
    });
  });

  it("stale_version: текст правки остаётся, повторное сохранение уходит с новой версией", async () => {
    const versions: number[] = [];
    let current = own("a1", "Кофе-поинт", 1);
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: [current] })),
      http.patch(apiUrl("/api/ideas/a1"), async ({ request }) => {
        const body = (await request.json()) as { version: number; title: string };
        versions.push(body.version);
        if (body.version !== current.version) {
          return problem({ code: "stale_version", status: 409 });
        }
        current = own("a1", body.title, current.version + 1);
        return HttpResponse.json(current);
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Править" }));
    // Другая вкладка успела сохранить версию 2.
    current = own("a1", "Правка из другой вкладки", 2);
    const form = screen.getByRole("form", { name: "Правка идеи" });
    const title = within(form).getByLabelText("Название");
    await user.clear(title);
    await user.type(title, "Моя правка");
    await user.click(within(form).getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText(/Идею изменили в другом окне/)).toBeInTheDocument();
    expect(within(form).getByLabelText("Название")).toHaveValue("Моя правка");

    await user.click(within(form).getByRole("button", { name: "Сохранить" }));
    await waitFor(() => {
      expect(versions).toEqual([1, 2]);
    });
    expect(await screen.findByRole("heading", { name: "Моя правка" })).toBeInTheDocument();
  });

  it("форма скрыта, если сервер не разрешил подачу", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", []))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: [] })),
    );
    renderApp("/contests/7");
    await screen.findByText("Вы ещё не предложили идей");
    expect(screen.queryByRole("form", { name: "Новая идея" })).not.toBeInTheDocument();
  });

  it("несуществующий конкурс и неверный адрес", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests/404"), () =>
        problem({ code: "contest_not_found", status: 404 }),
      ),
    );
    renderApp("/contests/404");
    expect(await screen.findByRole("heading", { name: "Конкурс не найден" })).toBeInTheDocument();
  });

  it("удаление своей идеи требует подтверждения", async () => {
    let ideas = [own("a1", "Кофе-поинт")];
    let deletes = 0;
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", ["submit_idea"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "submission", items: ideas })),
      http.delete(apiUrl("/api/ideas/a1"), () => {
        deletes += 1;
        ideas = [];
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Удалить" }));
    expect(deletes).toBe(0);
    await user.click(screen.getByRole("button", { name: "Нет" }));
    expect(screen.getByRole("button", { name: "Удалить" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Удалить" }));
    await user.click(screen.getByRole("button", { name: "Да, удалить" }));
    expect(await screen.findByText("Вы ещё не предложили идей")).toBeInTheDocument();
    expect(deletes).toBe(1);
  });
});

describe("страница конкурса: голосование", () => {
  const voting = (items: unknown[]) =>
    http.get(ideasUrl, () => HttpResponse.json({ phase: "voting", items }));

  it("кнопки по состоянию голоса; у своей идеи голосовать нельзя", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", ["vote"]))),
      voting([
        votable("b1", "Чужая без голоса"),
        votable("b2", "Чужая с голосом", false, true),
        votable("b3", "Моя идея", true),
      ]),
    );
    renderApp("/contests/7");
    const list = await screen.findByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(
      within(items[0] as HTMLElement).getByRole("button", { name: "Проголосовать" }),
    ).toBeEnabled();
    expect(
      within(items[1] as HTMLElement).getByRole("button", { name: "Отозвать голос" }),
    ).toBeEnabled();
    expect(within(items[2] as HTMLElement).queryByRole("button", { name: /голос/i })).toBeNull();
    expect(within(items[2] as HTMLElement).getByText(/Это ваша идея/)).toBeInTheDocument();
    // Авторов и времени подачи в голосовании на экране нет.
    expect(screen.queryByText(/Подана/)).not.toBeInTheDocument();
  });

  it("голос и отзыв вызывают PUT и DELETE и перечитывают список", async () => {
    const calls: string[] = [];
    let voted = false;
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", ["vote"]))),
      http.get(ideasUrl, () =>
        HttpResponse.json({ phase: "voting", items: [votable("b1", "Идея", false, voted)] }),
      ),
      http.put(apiUrl("/api/ideas/b1/vote"), () => {
        calls.push("PUT");
        voted = true;
        return new HttpResponse(null, { status: 204 });
      }),
      http.delete(apiUrl("/api/ideas/b1/vote"), () => {
        calls.push("DELETE");
        voted = false;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Проголосовать" }));
    await user.click(await screen.findByRole("button", { name: "Отозвать голос" }));
    await screen.findByRole("button", { name: "Проголосовать" });
    expect(calls).toEqual(["PUT", "DELETE"]);
  });

  it("404 на голос: «Идея удалена автором», идея исчезает из списка", async () => {
    let ideas = [votable("b1", "Исчезающая"), votable("b2", "Остающаяся")];
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", ["vote"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "voting", items: ideas })),
      http.put(apiUrl("/api/ideas/b1/vote"), () => {
        ideas = [votable("b2", "Остающаяся")];
        return problem({ code: "idea_not_found", status: 404 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    const [first] = await screen.findAllByRole("button", { name: "Проголосовать" });
    await user.click(first as HTMLElement);
    await waitFor(() => {
      expect(screen.queryByText("Исчезающая")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Остающаяся")).toBeInTheDocument();
  });

  it("voting_closed: перечитывает конкурс и показывает итоги", async () => {
    let closed = false;
    server.use(
      asEmployee,
      http.get(contestUrl, () =>
        HttpResponse.json(
          closed ? contest("finished", ["view_results"]) : contest("voting", ["vote"]),
        ),
      ),
      http.get(ideasUrl, () =>
        closed
          ? HttpResponse.json({ phase: "finished", items: [] })
          : HttpResponse.json({ phase: "voting", items: [votable("b1", "Идея")] }),
      ),
      http.get(apiUrl("/api/contests/7/results"), () =>
        HttpResponse.json({ status: "final", results: [] }),
      ),
      http.put(apiUrl("/api/ideas/b1/vote"), () => {
        closed = true;
        return problem({ code: "voting_closed", status: 409 });
      }),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Проголосовать" }));
    expect(await screen.findByText("Завершён")).toBeInTheDocument();
    expect(await screen.findByText("В конкурсе не было ни одной идеи.")).toBeInTheDocument();
    // Форма и кнопка исчезли вместе с фазой, поэтому причину показывает страница (П2).
    expect(screen.getByText(/Голосование закрыто\. Действие не выполнено/)).toBeInTheDocument();
  });

  it("все идеи свои — «Голосовать не за что»; своя идея удаляется с предупреждением о голосах", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", ["vote"]))),
      voting([votable("b1", "Моя идея", true)]),
    );
    renderApp("/contests/7");
    const user = userEvent.setup();
    expect(await screen.findByText(/Голосовать не за что/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Удалить" }));
    expect(screen.getByText(/Голоса за неё тоже будут удалены/)).toBeInTheDocument();
  });

  it("идей нет — «Идей нет»", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", ["vote"]))),
      voting([]),
    );
    renderApp("/contests/7");
    expect(await screen.findByRole("heading", { name: "Идей нет" })).toBeInTheDocument();
  });

  it("кнопок голоса нет, если сервер не разрешил голосовать", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", []))),
      voting([votable("b1", "Идея")]),
    );
    renderApp("/contests/7");
    await screen.findByText("Идея");
    expect(screen.queryByRole("button", { name: "Проголосовать" })).not.toBeInTheDocument();
  });
});

describe("страница конкурса: итоги", () => {
  it("после финала — места, голоса и авторы", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("finished", ["view_results"]))),
      http.get(ideasUrl, () => HttpResponse.json({ phase: "finished", items: [] })),
      http.get(apiUrl("/api/contests/7/results"), () =>
        HttpResponse.json({
          status: "final",
          results: [
            { place: 1, idea_id: "b1", title: "Победитель", votes: 3, author_name: "Анна" },
            { place: 2, idea_id: "b2", title: "Второй", votes: 1, author_name: "Борис" },
          ],
        }),
      ),
    );
    renderApp("/contests/7");
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("1Победитель");
    expect(rows[1]).toHaveTextContent("Анна");
    expect(rows[2]).toHaveTextContent("Борис");
    expect(screen.getByRole("columnheader", { name: "Автор" })).toBeInTheDocument();
  });
});

describe("страница конкурса: экран организатора", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("показывает число идей и проголосовавших, места без авторов", async () => {
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", []))),
      http.get(apiUrl("/api/organizer/contests/7/dashboard"), () =>
        HttpResponse.json({
          ideas_count: 2,
          voters_count: 5,
          results: [
            { place: 1, idea_id: "b1", title: "Лидер", votes: 4 },
            { place: 2, idea_id: "b2", title: "Второй", votes: 1 },
          ],
        }),
      ),
    );
    renderApp("/contests/7");
    expect(await screen.findByText("Лидер")).toBeInTheDocument();
    expect(screen.getByText("Идей подано").nextElementSibling).toHaveTextContent("2");
    expect(screen.getByText("Проголосовало").nextElementSibling).toHaveTextContent("5");
    expect(screen.queryByRole("columnheader", { name: "Автор" })).not.toBeInTheDocument();
    // Организатор не подаёт и не голосует: форм и кнопок голоса нет.
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });

  it("пустой конкурс", async () => {
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("submission", []))),
      http.get(apiUrl("/api/organizer/contests/7/dashboard"), () =>
        HttpResponse.json({ ideas_count: 0, voters_count: 0, results: [] }),
      ),
    );
    renderApp("/contests/7");
    expect(await screen.findByRole("heading", { name: "Идей пока нет" })).toBeInTheDocument();
  });

  it("обновляется при возвращении на вкладку; при сбое остаются последние цифры и баннер", async () => {
    let calls = 0;
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("voting", []))),
      http.get(apiUrl("/api/organizer/contests/7/dashboard"), () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json({ ideas_count: 1, voters_count: 0, results: [] });
        }
        if (calls === 2) {
          return HttpResponse.json({ ideas_count: 1, voters_count: 3, results: [] });
        }
        return problem({ code: "service_unavailable", status: 503 });
      }),
    );
    renderApp("/contests/7");
    await screen.findByText("Проголосовало");
    expect(screen.getByText("Проголосовало").nextElementSibling).toHaveTextContent("0");

    returnToTab();
    await waitFor(() => {
      expect(screen.getByText("Проголосовало").nextElementSibling).toHaveTextContent("3");
    });

    returnToTab();
    expect(await screen.findByText(/Не удалось обновить данные/)).toBeInTheDocument();
    expect(screen.getByText("Проголосовало").nextElementSibling).toHaveTextContent("3");
  });

  it("после финала организатор видит итоги с авторами", async () => {
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("finished", ["view_results"]))),
      http.get(apiUrl("/api/organizer/contests/7/dashboard"), () =>
        HttpResponse.json({ ideas_count: 1, voters_count: 1, results: [] }),
      ),
      http.get(apiUrl("/api/contests/7/results"), () =>
        HttpResponse.json({
          status: "final",
          results: [{ place: 1, idea_id: "b1", title: "Идея", votes: 1, author_name: "Анна" }],
        }),
      ),
    );
    renderApp("/contests/7");
    expect(await screen.findByRole("columnheader", { name: "Автор" })).toBeInTheDocument();
    expect(screen.getByText("Анна")).toBeInTheDocument();
  });
});
