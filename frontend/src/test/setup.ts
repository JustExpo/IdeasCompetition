// Пояс фиксирован до первого использования Date: тесты времени не зависят от машины.
process.env.TZ = "Europe/Moscow";

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { resetBuildObservation } from "../api";
import { installFakeWebSocket } from "./fakeWebSocket";
import { server } from "./server";

// Неописанный запрос — ошибка теста: так не пропустить обращение к реальной сети.
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
// Экраны конкурса открывают WebSocket сами, а настоящего сервера в тестах нет: сокет подменён
// во всех тестах, нужное поведение тест задаёт через `FakeWebSocket`.
beforeEach(() => {
  installFakeWebSocket();
  resetBuildObservation();
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  vi.unstubAllGlobals();
});
afterAll(() => {
  server.close();
});
