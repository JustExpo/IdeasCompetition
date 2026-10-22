import { describe, expect, it } from "vitest";

import {
  ApiError,
  createApiError,
  describeError,
  formatWait,
  isRetryableError,
  kindOfStatus,
  type ErrorKind,
} from "./errors";

function apiError(
  status: number,
  code: string,
  extra: Partial<ConstructorParameters<typeof ApiError>[0]> = {},
): ApiError {
  return new ApiError({ status, code, title: "title", requestId: "req-1", ...extra });
}

describe("kindOfStatus", () => {
  it.each<[number, ErrorKind]>([
    [401, "unauthenticated"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [400, "validation"],
    [413, "validation"],
    [415, "validation"],
    [422, "validation"],
    [429, "rate_limited"],
    [503, "unavailable"],
    [500, "server"],
    [502, "server"],
    [418, "unknown"],
  ])("статус %i → %s", (status, kind) => {
    expect(kindOfStatus(status)).toBe(kind);
  });
});

describe("describeError", () => {
  it("401: известный код даёт русский текст", () => {
    const description = describeError(apiError(401, "invalid_credentials"));
    expect(description.kind).toBe("unauthenticated");
    expect(description.message).toBe("Неверный e-mail или пароль.");
  });

  it("403: текст по коду", () => {
    const description = describeError(apiError(403, "organizer_cannot_participate"));
    expect(description.kind).toBe("forbidden");
    expect(description.message).toBe("Организатор не подаёт идеи и не голосует.");
  });

  it("404: текст по коду", () => {
    expect(describeError(apiError(404, "contest_not_found"))).toMatchObject({
      kind: "not_found",
      message: "Конкурс не найден.",
    });
  });

  it("409: текст по коду", () => {
    expect(describeError(apiError(409, "submission_closed"))).toMatchObject({
      kind: "conflict",
      message: "Приём идей закрыт.",
    });
  });

  it("422: ошибки по полям берутся из errors[], а неизвестный тип получает общий текст", () => {
    const description = describeError(
      apiError(422, "validation_error", {
        fieldErrors: [
          { field: "topic", code: "missing" },
          { field: "description", code: "something_new" },
        ],
      }),
    );
    expect(description.kind).toBe("validation");
    expect(description.fieldErrors).toEqual({
      topic: "Заполните поле.",
      description: "Проверьте введённые данные.",
    });
  });

  it("422: бизнес-код привязывается к полю формы", () => {
    expect(describeError(apiError(422, "email_taken")).fieldErrors).toEqual({
      email: "Этот e-mail уже зарегистрирован.",
    });
    expect(describeError(apiError(422, "deadlines_order")).fieldErrors).toHaveProperty(
      "voting_deadline",
    );
    expect(describeError(apiError(422, "deadline_in_past")).fieldErrors).toHaveProperty(
      "submission_deadline",
    );
  });

  it("429: к тексту добавляется время ожидания из Retry-After", () => {
    const description = describeError(
      apiError(429, "too_many_attempts", { retryAfterSeconds: 900 }),
    );
    expect(description.kind).toBe("rate_limited");
    expect(description.retryAfterSeconds).toBe(900);
    expect(description.message).toBe("Слишком много попыток. Повторите через 15 мин.");
  });

  it("429 без Retry-After: просто текст", () => {
    expect(describeError(apiError(429, "too_many_attempts")).message).toBe(
      "Слишком много попыток.",
    );
  });

  it("503: подсказка повторить, без кода запроса", () => {
    const description = describeError(
      apiError(503, "service_unavailable", { retryAfterSeconds: 5 }),
    );
    expect(description.kind).toBe("unavailable");
    expect(description.message).toBe(
      "Сервис временно недоступен. Повторите через несколько секунд. Повторите через 5 с.",
    );
  });

  it("500: текст и код запроса для обращения в поддержку", () => {
    const description = describeError(apiError(500, "internal_error", { requestId: "abc-123" }));
    expect(description.kind).toBe("server");
    expect(description.message).toBe("Внутренняя ошибка. Попробуйте позже. Код запроса: abc-123.");
  });

  it("неизвестный code → общий текст с request_id", () => {
    const description = describeError(apiError(409, "brand_new_code", { requestId: "req-77" }));
    expect(description.kind).toBe("conflict");
    expect(description.message).toBe("Не удалось выполнить действие. Код запроса: req-77.");
    expect(description.requestId).toBe("req-77");
  });

  it("неизвестный code без request_id → общий текст без кода", () => {
    const description = describeError(apiError(400, "brand_new_code", { requestId: null }));
    expect(description.message).toBe("Не удалось выполнить действие.");
  });

  it("сеть: TypeError от fetch", () => {
    expect(describeError(new TypeError("Failed to fetch")).kind).toBe("network");
  });

  it("прочее: общий текст", () => {
    const description = describeError(new Error("boom"));
    expect(description.kind).toBe("unknown");
    expect(description.message).not.toContain("boom");
  });

  it("название собственного свойства Object.prototype — не известный код", () => {
    expect(describeError(apiError(400, "constructor")).message).toBe(
      "Не удалось выполнить действие. Код запроса: req-1.",
    );
  });
});

describe("createApiError", () => {
  it("разбирает problem+json и Retry-After", () => {
    const response = new Response(null, { status: 429, headers: { "Retry-After": "900" } });
    const error = createApiError(response, {
      code: "too_many_attempts",
      title: "Слишком много попыток.",
      request_id: "r-1",
      errors: [{ field: "email", code: "x" }, { broken: true }, "text"],
    });
    expect(error).toMatchObject({
      status: 429,
      code: "too_many_attempts",
      requestId: "r-1",
      retryAfterSeconds: 900,
      fieldErrors: [{ field: "email", code: "x" }],
    });
  });

  it("тело не JSON: код unknown_error, request_id из заголовка", () => {
    const response = new Response(null, {
      status: 502,
      statusText: "Bad Gateway",
      headers: { "X-Request-ID": "hdr-1" },
    });
    const error = createApiError(response, "<html>proxy error</html>");
    expect(error).toMatchObject({ status: 502, code: "unknown_error", requestId: "hdr-1" });
    expect(describeError(error).message).toBe("Не удалось выполнить действие. Код запроса: hdr-1.");
  });

  it("Retry-After в формате даты игнорируется", () => {
    const response = new Response(null, {
      status: 503,
      headers: { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" },
    });
    expect(createApiError(response, {}).retryAfterSeconds).toBeNull();
  });
});

describe("isRetryableError", () => {
  it("повторяются сбои сервера и сети, но не ошибки клиента", () => {
    expect(isRetryableError(apiError(500, "internal_error"))).toBe(true);
    expect(isRetryableError(apiError(503, "service_unavailable"))).toBe(true);
    expect(isRetryableError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isRetryableError(apiError(401, "not_authenticated"))).toBe(false);
    expect(isRetryableError(apiError(409, "voting_closed"))).toBe(false);
    expect(isRetryableError(apiError(429, "too_many_attempts"))).toBe(false);
    expect(isRetryableError(new Error("bug"))).toBe(false);
  });
});

describe("formatWait", () => {
  it("секунды, минуты, округление вверх", () => {
    expect(formatWait(0)).toBe("1 с");
    expect(formatWait(5)).toBe("5 с");
    expect(formatWait(59)).toBe("59 с");
    expect(formatWait(59.2)).toBe("1 мин");
    expect(formatWait(60)).toBe("1 мин");
    expect(formatWait(61)).toBe("2 мин");
    expect(formatWait(3600)).toBe("60 мин");
  });
});
