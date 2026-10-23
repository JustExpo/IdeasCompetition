import createClient from "openapi-fetch";

import { observeBuild, observeMode } from "./build";
import { createApiError } from "./errors";
import type { paths } from "./schema.gen";

/**
 * Единственный HTTP-клиент SPA. Origin тот же, что у страницы: backend отдаёт SPA сам (Р1),
 * в разработке запросы идут через прокси Vite. Абсолютный базовый адрес нужен и тестам:
 * `fetch` в Node не принимает относительные адреса.
 */
export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // `fetch` берётся при каждом вызове, а не при создании клиента: так его можно подменить
  // (MSW в тестах ставит перехват уже после загрузки модулей).
  fetch: (request) => fetch(request),
});

// Сборка сервера по заголовку ответа: если сервер обновили, пока страница открыта, вкладка
// предложит перезагрузиться.
apiClient.use({
  onResponse({ response }) {
    observeBuild(response.headers.get("X-App-Build"));
    observeMode(response.headers.get("X-App-Mode"));
  },
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
