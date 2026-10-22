// Пояс фиксирован до первого использования Date: тесты времени не зависят от машины.
process.env.TZ = "Europe/Moscow";

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// Неописанный запрос — ошибка теста: так не пропустить обращение к реальной сети.
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});
