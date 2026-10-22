import { describe, expect, it } from "vitest";

import openapi from "../../openapi.json";

const paths = Object.keys(openapi.paths);

describe("контракт API (openapi.json)", () => {
  it("содержит маршруты входа, на которые опирается SPA", () => {
    expect(paths).toEqual(
      expect.arrayContaining([
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/register",
      ]),
    );
  });

  it("временный контракт конкурсов (pendingContracts.ts) удалён, когда маршруты появились", () => {
    // Если тест упал: IC-010 вошёл в main. Выполните `make contract`, удалите
    // src/api/pendingContracts.ts и `PendingPaths` в client.ts, возьмите типы из schema.gen.ts.
    expect(paths.filter((path) => path.startsWith("/api/contests"))).toEqual([]);
  });
});
