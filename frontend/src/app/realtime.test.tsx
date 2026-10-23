import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { connectContestEvents, type ContestEvent } from "../api";
import { renderApp } from "../test/render";
import { FakeWebSocket } from "../test/fakeWebSocket";
import { apiUrl, employee, http, HttpResponse, organizer, server } from "../test/server";

const contestUrl = apiUrl("/api/contests/7");
const dashboardUrl = apiUrl("/api/organizer/contests/7/dashboard");

function contest(phase: "submission" | "voting" | "finished") {
  return {
    id: 7,
    topic: "Как улучшить офис",
    description: "Любые идеи",
    created_at: "2026-10-20T10:00:00+00:00",
    submission_deadline: "2099-01-01T12:00:00+00:00",
    voting_deadline: "2099-01-02T12:00:00+00:00",
    phase,
    server_time: new Date().toISOString(),
    allowed_actions: [],
    tie_break_rule: "При равенстве голосов побеждает идея, поданная раньше.",
  };
}

function hello(build = "build-1") {
  return { v: 1, type: "hello", build };
}

/** Сервер принял соединение страницы и поздоровался. */
async function openSocket(): Promise<FakeWebSocket> {
  await waitFor(() => {
    expect(FakeWebSocket.instances.length).toBeGreaterThan(0);
  });
  const socket = FakeWebSocket.last;
  act(() => {
    socket.serverOpens();
    socket.serverSends(hello());
  });
  return socket;
}

const asOrganizer = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(organizer));
const asEmployee = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(employee));

describe("страница конкурса: обновления по WebSocket", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("подключается к событиям своего конкурса", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(apiUrl("/api/contests/7/ideas"), () =>
        HttpResponse.json({ phase: "voting", items: [] }),
      ),
    );
    renderApp("/contests/7");
    await openSocket();
    expect(FakeWebSocket.last.url).toMatch(/^ws:\/\/.+\/api\/contests\/7\/events$/);
  });

  it("results_changed перечитывает экран организатора без перезагрузки страницы", async () => {
    let calls = 0;
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(dashboardUrl, () => {
        calls += 1;
        return HttpResponse.json({ ideas_count: calls, voters_count: 0, results: [] });
      }),
    );
    renderApp("/contests/7");
    await screen.findByText("Идей подано");
    expect(screen.getByText("Идей подано").nextElementSibling).toHaveTextContent("1");
    const socket = await openSocket();
    act(() => {
      socket.serverSends({ v: 1, type: "results_changed", contest_id: 7 });
    });
    await waitFor(() => {
      expect(screen.getByText("Идей подано").nextElementSibling).toHaveTextContent("2");
    });
  });

  it("idea_deleted убирает идею из списка у другого пользователя", async () => {
    let deleted = false;
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(apiUrl("/api/contests/7/ideas"), () =>
        HttpResponse.json({
          phase: "voting",
          items: deleted
            ? []
            : [{ id: "i1", title: "Кофе-поинт", description: "д", is_mine: false, my_vote: false }],
        }),
      ),
    );
    renderApp("/contests/7");
    expect(await screen.findByText("Кофе-поинт")).toBeInTheDocument();
    const socket = await openSocket();
    deleted = true;
    act(() => {
      socket.serverSends({ v: 1, type: "idea_deleted", contest_id: 7, idea_id: "i1" });
    });
    await waitFor(() => {
      expect(screen.queryByText("Кофе-поинт")).not.toBeInTheDocument();
    });
  });

  it("ideas_changed перечитывает список идей", async () => {
    let titles = ["Первая"];
    server.use(
      asEmployee,
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(apiUrl("/api/contests/7/ideas"), () =>
        HttpResponse.json({
          phase: "voting",
          items: titles.map((title, index) => ({
            id: `i${String(index)}`,
            title,
            description: "д",
            is_mine: false,
            my_vote: index === 0,
          })),
        }),
      ),
    );
    renderApp("/contests/7");
    await screen.findByText("Первая");
    const socket = await openSocket();
    titles = ["Первая", "Вторая"];
    act(() => {
      socket.serverSends({ v: 1, type: "ideas_changed", contest_id: 7 });
    });
    expect(await screen.findByText("Вторая")).toBeInTheDocument();
  });

  it("без связи показывает предупреждение, после восстановления перечитывает всё", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      asOrganizer,
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(dashboardUrl, () => {
        calls += 1;
        return HttpResponse.json({ ideas_count: calls, voters_count: 0, results: [] });
      }),
    );
    renderApp("/contests/7");
    await screen.findByText("Идей подано");
    const first = await openSocket();
    act(() => {
      first.serverCloses(1006);
    });
    expect(await screen.findByText(/Нет связи с сервером/)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);
    const second = FakeWebSocket.last;
    act(() => {
      second.serverOpens();
    });
    await waitFor(() => {
      expect(screen.queryByText(/Нет связи с сервером/)).not.toBeInTheDocument();
    });
    // События за разрыв потеряны, поэтому после восстановления данные перечитаны.
    await waitFor(() => {
      expect(screen.getByText("Идей подано").nextElementSibling).toHaveTextContent("2");
    });
  });

  it("закрытие 4401 возвращает на вход", async () => {
    let signedIn = true;
    server.use(
      http.get(apiUrl("/api/auth/me"), () =>
        signedIn
          ? HttpResponse.json(employee)
          : HttpResponse.json(
              { code: "not_authenticated", status: 401, title: "Нужен вход" },
              {
                status: 401,
                headers: { "Content-Type": "application/problem+json" },
              },
            ),
      ),
      http.get(contestUrl, () => HttpResponse.json(contest("voting"))),
      http.get(apiUrl("/api/contests/7/ideas"), () =>
        HttpResponse.json({ phase: "voting", items: [] }),
      ),
    );
    renderApp("/contests/7");
    const socket = await openSocket();
    signedIn = false;
    act(() => {
      socket.serverCloses(4401);
    });
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent(/^\/login/);
    });
  });

  it("предлагает обновить страницу, когда сервер сообщил другую сборку", async () => {
    server.use(
      asEmployee,
      http.get(contestUrl, () =>
        HttpResponse.json(contest("voting"), { headers: { "X-App-Build": "build-1" } }),
      ),
      http.get(apiUrl("/api/contests/7/ideas"), () =>
        HttpResponse.json({ phase: "voting", items: [] }),
      ),
    );
    renderApp("/contests/7");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Как улучшить офис/ })).toBeInTheDocument();
    });
    const socket = await openSocket(); // приветствие с build-1 совпадает
    expect(screen.queryByText(/Доступна новая версия/)).not.toBeInTheDocument();
    act(() => {
      socket.serverCloses(1012);
    });
    act(() => {
      socket.serverSends(hello("build-2")); // после перезапуска сервер уже новой сборки
    });
    expect(await screen.findByText(/Доступна новая версия/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить страницу" })).toBeInTheDocument();
  });
});

describe("connectContestEvents", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function handlers() {
    return {
      events: [] as ContestEvent[],
      statuses: [] as string[],
      resyncs: 0,
      ended: 0,
    };
  }

  function connect(state: ReturnType<typeof handlers>) {
    return connectContestEvents(
      7,
      {
        onEvent: (event) => state.events.push(event),
        onStatus: (status) => state.statuses.push(status),
        onResync: () => {
          state.resyncs += 1;
        },
        onSessionEnded: () => {
          state.ended += 1;
        },
      },
      { retryDelaysMs: [10, 20], pingIntervalMs: 50 },
    );
  }

  it("разбирает только известные сообщения нужного вида", () => {
    const state = handlers();
    const stop = connect(state);
    const socket = FakeWebSocket.last;
    socket.serverOpens();
    socket.serverSends({ v: 1, type: "ideas_changed", contest_id: 7 });
    socket.serverSends({ v: 1, type: "idea_deleted", contest_id: 7, idea_id: "i1" });
    socket.serverSends({ v: 1, type: "unknown_type", contest_id: 7 });
    socket.serverSends({ v: 1, type: "ideas_changed" }); // без конкурса
    socket.onmessage?.(new MessageEvent("message", { data: "not json" }));
    expect(state.events).toEqual([
      { type: "ideas_changed", contestId: 7 },
      { type: "idea_deleted", contestId: 7, ideaId: "i1" },
    ]);
    stop();
  });

  it("первое подключение не требует перечитывания, повторное — требует", async () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    FakeWebSocket.last.serverOpens();
    expect(state.resyncs).toBe(0);
    FakeWebSocket.last.serverCloses(1012);
    await vi.advanceTimersByTimeAsync(15);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.last.serverOpens();
    expect(state.resyncs).toBe(1);
    stop();
  });

  it("пауза между попытками растёт и сбрасывается после успеха", async () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    FakeWebSocket.last.serverCloses(1006); // попытка 1 → ждём 10 мс
    await vi.advanceTimersByTimeAsync(9);
    expect(FakeWebSocket.instances).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(2);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.last.serverCloses(1006); // попытка 2 → ждём 20 мс
    await vi.advanceTimersByTimeAsync(15);
    expect(FakeWebSocket.instances).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(10);
    expect(FakeWebSocket.instances).toHaveLength(3);
    FakeWebSocket.last.serverOpens(); // успех сбрасывает счётчик
    FakeWebSocket.last.serverCloses(1006);
    await vi.advanceTimersByTimeAsync(11);
    expect(FakeWebSocket.instances).toHaveLength(4);
    stop();
  });

  it("4401 не переподключается и сообщает об окончании сессии", async () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    FakeWebSocket.last.serverOpens();
    FakeWebSocket.last.serverCloses(4401);
    await vi.advanceTimersByTimeAsync(100);
    expect(state.ended).toBe(1);
    expect(FakeWebSocket.instances).toHaveLength(1);
    stop();
  });

  it("шлёт ping, пока соединение открыто, и перестаёт после отключения", async () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    const socket = FakeWebSocket.last;
    socket.serverOpens();
    await vi.advanceTimersByTimeAsync(120);
    expect(socket.sent).toEqual(["ping", "ping"]);
    stop();
    await vi.advanceTimersByTimeAsync(200);
    expect(socket.sent).toHaveLength(2);
  });

  it("возвращение на вкладку подключает сразу, не дожидаясь паузы", () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    FakeWebSocket.last.serverCloses(1006);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(FakeWebSocket.instances).toHaveLength(2);
    stop();
  });

  it("после отключения не переподключается и закрывает сокет", async () => {
    vi.useFakeTimers();
    const state = handlers();
    const stop = connect(state);
    const socket = FakeWebSocket.last;
    socket.serverOpens();
    stop();
    expect(socket.readyState).toBe(FakeWebSocket.CLOSED);
    socket.serverCloses(1006);
    await vi.advanceTimersByTimeAsync(100);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
