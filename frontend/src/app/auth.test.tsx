import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderApp } from "../test/render";
import { apiUrl, employee, http, HttpResponse, problem, server } from "../test/server";
import { resolveReturnPath } from "../features/auth";

const noContests = http.get(apiUrl("/api/contests"), () =>
  HttpResponse.json({ items: [], total: 0 }),
);
const signedOut = http.get(apiUrl("/api/auth/me"), () =>
  problem({ code: "not_authenticated", status: 401 }),
);
const signedIn = http.get(apiUrl("/api/auth/me"), () => HttpResponse.json(employee));

async function fillLogin(email: string, password: string): Promise<void> {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("E-mail"), email);
  await user.type(screen.getByLabelText("Пароль"), password);
  await user.click(screen.getByRole("button", { name: "Войти" }));
}

describe("защита маршрутов", () => {
  it("без сессии уводит на вход, после входа возвращает на исходный адрес", async () => {
    server.use(signedOut, noContests);
    server.use(http.post(apiUrl("/api/auth/login"), () => HttpResponse.json(employee)));
    renderApp("/?page=2");

    expect(await screen.findByRole("heading", { name: "Вход" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");

    await fillLogin("ivan@example.com", "correct-horse-battery");

    expect(await screen.findByRole("heading", { name: "Конкурсы" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/?page=2");
  });

  it("вошедший пользователь видит приложение, а страница входа его не держит", async () => {
    server.use(signedIn, noContests);
    renderApp("/login");
    expect(await screen.findByRole("heading", { name: "Конкурсы" })).toBeInTheDocument();
    expect(screen.getByText("Иван")).toBeInTheDocument();
  });

  it("сессия пропала посреди работы (401 not_authenticated): переход на вход", async () => {
    server.use(signedIn);
    server.use(
      http.get(apiUrl("/api/contests"), () => problem({ code: "not_authenticated", status: 401 })),
    );
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Вход" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it("сервер недоступен при проверке сессии: сообщение и повтор, а не вход", async () => {
    let attempts = 0;
    server.use(
      http.get(apiUrl("/api/auth/me"), () => {
        attempts += 1;
        return attempts === 1
          ? problem({ code: "service_unavailable", status: 503, retryAfter: 5 })
          : HttpResponse.json(employee);
      }),
      noContests,
    );
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервис временно недоступен");
    await userEvent.setup().click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByRole("heading", { name: "Конкурсы" })).toBeInTheDocument();
  });

  it("выход: сессия сбрасывается, открывается вход", async () => {
    server.use(signedIn, noContests);
    let loggedOut = false;
    server.use(
      http.post(apiUrl("/api/auth/logout"), () => {
        loggedOut = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderApp("/");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Выйти" }));
    expect(await screen.findByRole("heading", { name: "Вход" })).toBeInTheDocument();
    expect(loggedOut).toBe(true);
  });
});

describe("вход", () => {
  it("пустые поля: ошибки у полей, запрос не отправляется", async () => {
    server.use(signedOut);
    renderApp("/login");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Войти" }));
    expect(screen.getByText("Введите e-mail.")).toBeInTheDocument();
    expect(screen.getByText("Введите пароль.")).toBeInTheDocument();
  });

  it("invalid_credentials: сообщение над формой", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/login"), () =>
        problem({ code: "invalid_credentials", status: 401 }),
      ),
    );
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вход" });
    await fillLogin("ivan@example.com", "wrong-password");
    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный e-mail или пароль.");
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it("429: сообщение с временем ожидания из Retry-After", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/login"), () =>
        problem({ code: "too_many_attempts", status: 429, retryAfter: 900 }),
      ),
    );
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вход" });
    await fillLogin("ivan@example.com", "wrong-password");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Слишком много попыток. Повторите через 15 мин.",
    );
  });

  it("503: сообщение о недоступности", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/login"), () =>
        problem({ code: "service_unavailable", status: 503, retryAfter: 5 }),
      ),
    );
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вход" });
    await fillLogin("ivan@example.com", "password-123456");
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервис временно недоступен");
  });

  it("500 с неизвестным кодом: общий текст с кодом запроса", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/login"), () =>
        problem({ code: "something_new", status: 500, requestId: "req-500" }),
      ),
    );
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вход" });
    await fillLogin("ivan@example.com", "password-123456");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Не удалось выполнить действие. Код запроса: req-500.",
    );
  });

  it("обрыв сети: сообщение о связи", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/login"), () => HttpResponse.error()),
    );
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вход" });
    await fillLogin("ivan@example.com", "password-123456");
    expect(await screen.findByRole("alert")).toHaveTextContent("Нет связи с сервером");
  });
});

describe("регистрация", () => {
  async function fillRegister(email: string, password = "long-enough-password"): Promise<void> {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Имя"), "Иван");
    await user.type(screen.getByLabelText("E-mail"), email);
    await user.type(screen.getByLabelText("Пароль"), password);
    await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));
  }

  it("успех: сервер сразу открывает сессию, пользователь попадает в список", async () => {
    let body: unknown;
    server.use(
      signedOut,
      noContests,
      http.post(apiUrl("/api/auth/register"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(employee, { status: 201 });
      }),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@example.com");
    expect(await screen.findByRole("heading", { name: "Конкурсы" })).toBeInTheDocument();
    expect(body).toEqual({
      name: "Иван",
      email: "ivan@example.com",
      password: "long-enough-password",
    });
  });

  it("email_taken: ошибка у поля e-mail", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/register"), () => problem({ code: "email_taken", status: 409 })),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@example.com");
    expect(await screen.findByText("Этот e-mail уже зарегистрирован.")).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail")).toBeInvalid();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("email_domain_not_allowed: ошибка у поля e-mail", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/register"), () =>
        problem({ code: "email_domain_not_allowed", status: 422 }),
      ),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@gmail.com");
    expect(
      await screen.findByText("Регистрация доступна только с корпоративным e-mail."),
    ).toBeInTheDocument();
  });

  it("короткий пароль отклоняется до отправки", async () => {
    server.use(signedOut);
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@example.com", "short");
    expect(screen.getByText("Пароль — от 10 до 128 символов.")).toBeInTheDocument();
  });

  it("422 с ошибками по полям от сервера", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/register"), () =>
        problem({
          code: "validation_error",
          status: 422,
          errors: [{ field: "name", code: "string_too_long" }],
        }),
      ),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@example.com");
    expect(await screen.findByText("Слишком длинное значение.")).toBeInTheDocument();
  });

  it("429: сообщение над формой с временем ожидания", async () => {
    server.use(
      signedOut,
      http.post(apiUrl("/api/auth/register"), () =>
        problem({ code: "too_many_attempts", status: 429, retryAfter: 3600 }),
      ),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Регистрация" });
    await fillRegister("ivan@example.com");
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Повторите через 60 мин.");
    });
  });
});

describe("resolveReturnPath", () => {
  it.each([
    [{ from: { pathname: "/contests/5", search: "?a=1", hash: "#x" } }, "/contests/5?a=1#x"],
    [{ from: { pathname: "/" } }, "/"],
    [undefined, "/"],
    [null, "/"],
    ["/contests/5", "/"],
    [{ from: "/contests/5" }, "/"],
    [{ from: { pathname: "//evil.example" } }, "/"],
    [{ from: { pathname: "/\\evil.example" } }, "/"],
    [{ from: { pathname: "https://evil.example" } }, "/"],
    [{ from: { pathname: "/login" } }, "/"],
    [{ from: { pathname: "/register" } }, "/"],
    [{ from: { pathname: 42 } }, "/"],
  ])("%j → %s", (state, expected) => {
    expect(resolveReturnPath(state)).toBe(expected);
  });
});
