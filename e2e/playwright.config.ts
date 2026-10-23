import { defineConfig, devices } from "@playwright/test";

import { APP_URL } from "./support/env";

// Единственный `app` в режиме e2e (CLAUDE.md Р14): тесты делят одни тестовые часы, которые
// идут только вперёд, поэтому один воркер и последовательный порядок.
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: APP_URL,
    locale: "ru-RU",
    timezoneId: "UTC",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : {},
  },
});
