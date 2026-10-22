import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ContestSummary } from "../api";
import { renderApp } from "../test/render";
import {
  apiUrl,
  employee,
  http,
  HttpResponse,
  organizer,
  problem,
  server,
  type ProblemOptions,
} from "../test/server";

function contest(id: number, phase: ContestSummary["phase"] = "submission"): ContestSummary {
  return {
    id,
    topic: `Тема ${String(id)}`,
    description: "Описание",
    created_at: "2026-10-20T10:00:00+00:00",
    submission_deadline: "2026-10-24T15:00:00+00:00",
    voting_deadline: "2026-10-26T15:00:00+00:00",
    phase,
  };
}

const asEmployee = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(employee));
const asOrganizer = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(organizer));

describe("список конкурсов", () => {
  it("показывает конкурсы с фазами и дедлайнами в поясе браузера", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), () =>
        HttpResponse.json({
          items: [contest(1, "submission"), contest(2, "voting"), contest(3, "finished")],
          total: 3,
        }),
      ),
    );
    renderApp("/");
    const list = await screen.findByRole("list", { name: "Конкурсы" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0] as HTMLElement).getByRole("link", { name: "Тема 1" })).toHaveAttribute(
      "href",
      "/contests/1",
    );
    expect(items[0]).toHaveTextContent("Приём идей");
    expect(items[1]).toHaveTextContent("Голосование");
    expect(items[2]).toHaveTextContent("Завершён");
    // 15:00 UTC = 18:00 в Europe/Moscow
    expect(items[0]).toHaveTextContent("18:00");
  });

  it("пусто, сотрудник: пояснение без кнопки создания", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), () => HttpResponse.json({ items: [], total: 0 })),
    );
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Пока нет конкурсов" })).toBeInTheDocument();
    expect(screen.getByText("Когда организатор создаст конкурс, он появится здесь.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Создать конкурс" })).not.toBeInTheDocument();
  });

  it("пусто, организатор: подсказка создать первый конкурс", async () => {
    server.use(
      asOrganizer,
      http.get(apiUrl("/api/contests"), () => HttpResponse.json({ items: [], total: 0 })),
    );
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Пока нет конкурсов" })).toBeInTheDocument();
    expect(screen.getByText(/Создайте первый конкурс/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Создать конкурс" })).toBeVisible();
  });

  it("500: сообщение с кодом запроса и кнопка повтора", async () => {
    let attempts = 0;
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), () => {
        attempts += 1;
        return attempts === 1
          ? problem({ code: "internal_error", status: 500, requestId: "req-9" })
          : HttpResponse.json({ items: [contest(1)], total: 1 });
      }),
    );
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Код запроса: req-9");
    await userEvent.setup().click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByRole("link", { name: "Тема 1" })).toBeVisible();
  });

  it("503: сообщение о недоступности", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), () =>
        problem({ code: "service_unavailable", status: 503, retryAfter: 5 }),
      ),
    );
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервис временно недоступен");
  });

  it("403 и 404: текст по коду", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), () => problem({ code: "forbidden", status: 403 })),
    );
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Недостаточно прав");
  });

  it("постраничный просмотр: 25 конкурсов — вторая страница по offset", async () => {
    const requested: string[] = [];
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), ({ request }) => {
        const url = new URL(request.url);
        requested.push(
          `${url.searchParams.get("limit") ?? ""}/${url.searchParams.get("offset") ?? ""}`,
        );
        const offset = Number(url.searchParams.get("offset"));
        return HttpResponse.json({
          items: offset === 0 ? [contest(1)] : [contest(21)],
          total: 25,
        });
      }),
    );
    renderApp("/");
    await screen.findByRole("link", { name: "Тема 1" });
    expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: "Вперёд" }));
    expect(await screen.findByRole("link", { name: "Тема 21" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Вперёд" })).toBeDisabled();
    expect(requested).toEqual(["20/0", "20/20"]);
  });

  it("страница за концом списка: возврат к началу", async () => {
    server.use(
      asEmployee,
      http.get(apiUrl("/api/contests"), ({ request }) => {
        const offset = Number(new URL(request.url).searchParams.get("offset"));
        return offset === 0
          ? HttpResponse.json({ items: [contest(1)], total: 25 })
          : HttpResponse.json({ items: [], total: 25 });
      }),
    );
    renderApp("/");
    await screen.findByRole("link", { name: "Тема 1" });
    await userEvent.setup().click(screen.getByRole("button", { name: "Вперёд" }));
    await userEvent.setup().click(await screen.findByRole("button", { name: "К началу списка" }));
    expect(await screen.findByRole("link", { name: "Тема 1" })).toBeVisible();
  });
});

describe("создание конкурса", () => {
  const emptyList = http.get(apiUrl("/api/contests"), () =>
    HttpResponse.json({ items: [], total: 0 }),
  );

  async function openForm(): Promise<ReturnType<typeof userEvent.setup>> {
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Создать конкурс" }));
    return user;
  }

  async function fillForm(
    user: ReturnType<typeof userEvent.setup>,
    submission: string,
    voting: string,
  ): Promise<void> {
    await user.type(screen.getByLabelText("Тема"), "Как улучшить офис");
    await user.type(screen.getByLabelText("Описание"), "Любые идеи");
    await user.type(screen.getByLabelText("Приём идей закрывается"), submission);
    await user.type(screen.getByLabelText("Голосование закрывается"), voting);
    await user.click(screen.getByRole("button", { name: "Создать конкурс" }));
  }

  it("сотруднику кнопка создания не показывается", async () => {
    server.use(asEmployee, emptyList);
    renderApp("/");
    await screen.findByRole("heading", { name: "Конкурсы" });
    expect(screen.queryByRole("button", { name: "Создать конкурс" })).not.toBeInTheDocument();
  });

  it("успех: время уходит со смещением браузера, список обновляется, форма закрывается", async () => {
    let body: unknown;
    let created = false;
    server.use(
      asOrganizer,
      http.get(apiUrl("/api/contests"), () =>
        HttpResponse.json(created ? { items: [contest(7)], total: 1 } : { items: [], total: 0 }),
      ),
      http.post(apiUrl("/api/contests"), async ({ request }) => {
        body = await request.json();
        created = true;
        return HttpResponse.json(contest(7), { status: 201 });
      }),
    );
    renderApp("/");
    const user = await openForm();
    await fillForm(user, "2026-10-24T18:00", "2026-10-26T18:00");

    expect(await screen.findByRole("link", { name: "Тема 7" })).toBeVisible();
    expect(body).toEqual({
      topic: "Как улучшить офис",
      description: "Любые идеи",
      submission_deadline: "2026-10-24T18:00:00+03:00",
      voting_deadline: "2026-10-26T18:00:00+03:00",
    });
    expect(screen.queryByRole("form", { name: "Новый конкурс" })).not.toBeInTheDocument();
  });

  it("deadlines_order от сервера: ошибка у поля голосования", async () => {
    server.use(
      asOrganizer,
      emptyList,
      http.post(apiUrl("/api/contests"), () => problem({ code: "deadlines_order", status: 422 })),
    );
    renderApp("/");
    const user = await openForm();
    await fillForm(user, "2026-10-24T18:00", "2026-10-26T18:00");
    expect(
      await screen.findByText("Голосование должно закрываться позже, чем приём идей."),
    ).toBeVisible();
    expect(screen.getByLabelText("Голосование закрывается")).toBeInvalid();
  });

  it("deadline_in_past от сервера: ошибка у поля приёма идей", async () => {
    server.use(
      asOrganizer,
      emptyList,
      http.post(apiUrl("/api/contests"), () => problem({ code: "deadline_in_past", status: 422 })),
    );
    renderApp("/");
    const user = await openForm();
    await fillForm(user, "2020-10-24T18:00", "2026-10-26T18:00");
    expect(
      await screen.findByText("Срок приёма идей уже прошёл: выберите время в будущем."),
    ).toBeVisible();
    expect(screen.getByLabelText("Приём идей закрывается")).toBeInvalid();
  });

  it("порядок дедлайнов проверяется до отправки", async () => {
    let posted = false;
    server.use(
      asOrganizer,
      emptyList,
      http.post(apiUrl("/api/contests"), () => {
        posted = true;
        return HttpResponse.json(contest(1), { status: 201 });
      }),
    );
    renderApp("/");
    const user = await openForm();
    await fillForm(user, "2026-10-26T18:00", "2026-10-24T18:00");
    expect(screen.getByText("Голосование должно закрываться позже, чем приём идей.")).toBeVisible();
    expect(posted).toBe(false);
  });

  it("пустая тема и несуществующая дата отклоняются до отправки", async () => {
    server.use(asOrganizer, emptyList);
    renderApp("/");
    const user = await openForm();
    await user.click(screen.getByRole("button", { name: "Создать конкурс" }));
    expect(screen.getByText("Введите тему конкурса.")).toBeVisible();
    expect(screen.getAllByText("Укажите существующие дату и время.")).toHaveLength(2);
  });

  it.each<[string, ProblemOptions, string]>([
    ["403", { code: "forbidden", status: 403 }, "Недостаточно прав для этого действия."],
    [
      "429",
      { code: "too_many_attempts", status: 429, retryAfter: 60 },
      "Слишком много попыток. Повторите через 1 мин.",
    ],
    ["503", { code: "service_unavailable", status: 503 }, "Сервис временно недоступен."],
    [
      "500",
      { code: "internal_error", status: 500, requestId: "req-c" },
      "Внутренняя ошибка. Попробуйте позже. Код запроса: req-c.",
    ],
  ])("%s: сообщение над формой", async (_name, options, text) => {
    server.use(
      asOrganizer,
      emptyList,
      http.post(apiUrl("/api/contests"), () => problem(options)),
    );
    renderApp("/");
    const user = await openForm();
    await fillForm(user, "2026-10-24T18:00", "2026-10-26T18:00");
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(text);
    });
  });

  it("отмена закрывает форму", async () => {
    server.use(asOrganizer, emptyList);
    renderApp("/");
    const user = await openForm();
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(screen.queryByRole("form", { name: "Новый конкурс" })).not.toBeInTheDocument();
  });
});
