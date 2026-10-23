import { randomUUID } from "node:crypto";

import {
  expect,
  request,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
} from "@playwright/test";

import { APP_URL, ORGANIZER_EMAIL, ORGANIZER_PASSWORD, PASSWORD } from "./env";

export interface Person {
  email: string;
  name: string;
  api: APIRequestContext;
}

export interface ContestInfo {
  id: number;
  topic: string;
  submissionDeadline: Date;
  votingDeadline: Date;
}

/** Тот же `Origin`, что у SPA: сервер требует его для небезопасных методов (CSRF, §9.3). */
async function newApi(): Promise<APIRequestContext> {
  return request.newContext({ baseURL: APP_URL, extraHTTPHeaders: { Origin: APP_URL } });
}

export function uniqueSuffix(): string {
  return randomUUID().slice(0, 8);
}

export async function registerEmployee(label: string): Promise<Person> {
  const email = `${label}-${uniqueSuffix()}@example.com`;
  const name = `Сотрудник ${label}`;
  const api = await newApi();
  const response = await api.post("/api/auth/register", {
    data: { email, name, password: PASSWORD },
  });
  expect(response.status(), await response.text()).toBe(201);
  return { email, name, api };
}

export async function loginOrganizer(): Promise<Person> {
  const api = await newApi();
  const response = await api.post("/api/auth/login", {
    data: { email: ORGANIZER_EMAIL, password: ORGANIZER_PASSWORD },
  });
  expect(response.status(), await response.text()).toBe(200);
  return { email: ORGANIZER_EMAIL, name: "Организатор", api };
}

/** Контекст браузера с уже выполненным входом: cookie сессии берётся из API-клиента. */
export async function browserContextFor(browser: Browser, person: Person): Promise<BrowserContext> {
  return browser.newContext({ storageState: await person.api.storageState() });
}

/** Серверное «сейчас» (часы e2e могут быть сдвинуты). */
export async function serverNow(person: Person): Promise<Date> {
  const response = await person.api.get("/api/contests?limit=1");
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { server_time: string };
  return new Date(body.server_time);
}

export async function createContest(
  organizer: Person,
  topic: string,
  submissionInMs = 3_600_000,
  votingInMs = 7_200_000,
): Promise<ContestInfo> {
  const now = await serverNow(organizer);
  const submissionDeadline = new Date(now.getTime() + submissionInMs);
  const votingDeadline = new Date(now.getTime() + votingInMs);
  const response = await organizer.api.post("/api/contests", {
    data: {
      topic,
      description: "",
      submission_deadline: submissionDeadline.toISOString(),
      voting_deadline: votingDeadline.toISOString(),
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = (await response.json()) as { id: number };
  return { id: body.id, topic, submissionDeadline, votingDeadline };
}

export async function submitIdea(
  person: Person,
  contestId: number,
  title: string,
): Promise<string> {
  const response = await person.api.post(`/api/contests/${String(contestId)}/ideas`, {
    data: { title, description: `Описание: ${title}`, client_request_id: randomUUID() },
  });
  expect(response.status(), await response.text()).toBe(201);
  return ((await response.json()) as { id: string }).id;
}

export async function castVote(person: Person, ideaId: string): Promise<void> {
  const response = await person.api.put(`/api/ideas/${ideaId}/vote`);
  expect(response.status(), await response.text()).toBe(204);
}

/** Перевести тестовые часы вперёд; сервер сразу выполняет тик (финал, письма, напоминания). */
export async function moveClockTo(moment: Date): Promise<void> {
  const api = await newApi();
  const response = await api.post("/api/__test__/clock", { data: { now: moment.toISOString() } });
  expect(response.status(), await response.text()).toBe(204);
  await api.dispose();
}

export function after(moment: Date, ms: number): Date {
  return new Date(moment.getTime() + ms);
}
