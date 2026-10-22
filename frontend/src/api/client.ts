import createClient from "openapi-fetch";

import { createApiError } from "./errors";
import type { PendingPaths } from "./pendingContracts";
import type { paths } from "./schema.gen";

export type ApiPaths = paths & PendingPaths;

/**
 * Единственный HTTP-клиент SPA. Origin тот же, что у страницы: backend отдаёт SPA сам (Р1),
 * в разработке запросы идут через прокси Vite. Абсолютный базовый адрес нужен и тестам:
 * `fetch` в Node не принимает относительные адреса.
 */
export const apiClient = createClient<ApiPaths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // `fetch` берётся при каждом вызове, а не при создании клиента: так его можно подменить
  // (MSW в тестах ставит перехват уже после загрузки модулей).
  fetch: (request) => fetch(request),
});

interface RawResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Развернуть ответ openapi-fetch: успех → данные, иначе исключение `ApiError`. */
export function unwrap<T>(result: RawResult<T>): T {
  if (result.response.ok) {
    return result.data as T; // у ответов 204 тела нет, T тогда `never`/`undefined`
  }
  throw createApiError(result.response, result.error);
}
