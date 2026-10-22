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

  it("содержит маршруты конкурсов и идей, на которые опирается SPA", () => {
    expect(paths).toEqual(
      expect.arrayContaining([
        "/api/contests",
        "/api/contests/{contest_id}",
        "/api/contests/{contest_id}/ideas",
        "/api/ideas/{idea_id}",
      ]),
    );
  });
});
