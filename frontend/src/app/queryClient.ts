import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError, isRetryableError } from "../api";
import { sessionKey } from "../features/auth";

const MAX_RETRIES = 2;

/**
 * Единая реакция на потерю сессии (CLAUDE.md §8.1: 401 → вход): любой запрос, получивший
 * `not_authenticated`, обнуляет кэш пользователя, а `RequireAuth` уводит на экран входа
 * с возвратом на исходный адрес. `invalid_credentials` (тоже 401) сюда не относится.
 */
function handleSessionLoss(client: QueryClient, error: unknown): void {
  if (error instanceof ApiError && error.code === "not_authenticated") {
    client.setQueryData(sessionKey, null);
  }
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        handleSessionLoss(client, error);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error) => {
        handleSessionLoss(client, error);
      },
    }),
    defaultOptions: {
      queries: {
        // §8.3: повторяются только чтения, не более 2 раз и не при 4xx.
        retry: (failureCount, error) => failureCount < MAX_RETRIES && isRetryableError(error),
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
      },
      mutations: { retry: false },
    },
  });
  return client;
}
