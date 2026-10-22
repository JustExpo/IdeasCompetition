import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const server = setupServer();

/** Адрес API в тестах: тот же origin, что у страницы в jsdom. */
export function apiUrl(path: string): string {
  return new URL(path, window.location.origin).toString();
}

export interface ProblemOptions {
  code: string;
  status: number;
  title?: string;
  requestId?: string;
  errors?: { field: string; code: string }[];
  retryAfter?: number;
}

/** Ответ сервера об ошибке в формате problem+json (CLAUDE.md §8.1). */
export function problem(options: ProblemOptions): Response {
  const headers: Record<string, string> = { "Content-Type": "application/problem+json" };
  if (options.retryAfter !== undefined) {
    headers["Retry-After"] = String(options.retryAfter);
  }
  return HttpResponse.json(
    {
      type: `urn:ideas-competition:error:${options.code}`,
      title: options.title ?? "Ошибка",
      status: options.status,
      code: options.code,
      detail: null,
      request_id: options.requestId ?? "req-test-1",
      errors: options.errors ?? [],
    },
    { status: options.status, headers },
  );
}

export const employee = { id: 2, email: "ivan@example.com", name: "Иван", role: "employee" };
export const organizer = {
  id: 1,
  email: "org@example.com",
  name: "Организатор",
  role: "organizer",
};

export { http, HttpResponse };
