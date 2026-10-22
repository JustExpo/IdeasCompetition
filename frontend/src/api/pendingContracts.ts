/**
 * ВРЕМЕННЫЙ контракт `/api/contests` по CLAUDE.md §8.2.
 *
 * Backend конкурсов (IC-010) ещё не вошёл в `main`, поэтому в `openapi.json` этих маршрутов нет,
 * а ручных TS-типов ответов в проекте быть не должно (§8.1). Пока маршрутов нет, форма ответа
 * описана здесь. Когда IC-010 вольётся: `make contract`, удалить этот файл и `PendingPaths`
 * из `client.ts` — тест `contract.test.ts` упадёт ровно в этот момент и напомнит об этом.
 */

export type ContestPhase = "submission" | "voting" | "finished";

export interface ContestSummary {
  id: number;
  topic: string;
  submission_deadline: string;
  voting_deadline: string;
  phase: ContestPhase;
}

export interface ContestList {
  items: ContestSummary[];
  total: number;
}

export interface ContestCreateRequest {
  topic: string;
  description: string;
  submission_deadline: string;
  voting_deadline: string;
}

interface NoParameters {
  query?: never;
  header?: never;
  path?: never;
  cookie?: never;
}

export interface PendingPaths {
  "/api/contests": {
    parameters: NoParameters;
    get: {
      parameters: {
        query?: { limit?: number; offset?: number };
        header?: never;
        path?: never;
        cookie?: never;
      };
      requestBody?: never;
      responses: {
        200: { headers: Record<string, unknown>; content: { "application/json": ContestList } };
      };
    };
    put?: never;
    post: {
      parameters: NoParameters;
      requestBody: { content: { "application/json": ContestCreateRequest } };
      responses: {
        201: { headers: Record<string, unknown>; content: { "application/json": ContestSummary } };
      };
    };
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
