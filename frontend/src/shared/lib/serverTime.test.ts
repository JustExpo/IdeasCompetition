import { describe, expect, it } from "vitest";

import { createServerClock, msUntil } from "./serverTime";

const SERVER_TIME = "2026-10-24T12:00:00+00:00";
const SERVER_MS = Date.parse(SERVER_TIME);

describe("createServerClock", () => {
  it("до синхронизации совпадает с локальными часами", () => {
    const clock = createServerClock(() => 1_000);
    expect(clock.now()).toBe(1_000);
    expect(clock.offsetMs()).toBe(0);
  });

  it("часы клиента отстают на 5 минут: серверное время всё равно верное", () => {
    let local = SERVER_MS - 5 * 60_000;
    const clock = createServerClock(() => local);
    expect(clock.sync(SERVER_TIME)).toBe(true);
    expect(clock.offsetMs()).toBe(5 * 60_000);
    local += 10_000; // прошло 10 с
    expect(clock.now()).toBe(SERVER_MS + 10_000);
  });

  it("часы клиента спешат на 2 часа: смещение отрицательное", () => {
    const local = SERVER_MS + 2 * 3_600_000;
    const clock = createServerClock(() => local);
    clock.sync(SERVER_TIME);
    expect(clock.offsetMs()).toBe(-2 * 3_600_000);
    expect(clock.now()).toBe(SERVER_MS);
  });

  it("смещение пояса в строке учитывается", () => {
    const clock = createServerClock(() => SERVER_MS);
    clock.sync("2026-10-24T15:00:00+03:00");
    expect(clock.offsetMs()).toBe(0);
  });

  it("неразбираемое время игнорируется, прежнее смещение остаётся", () => {
    const clock = createServerClock(() => SERVER_MS - 1_000);
    clock.sync(SERVER_TIME);
    expect(clock.sync("вчера")).toBe(false);
    expect(clock.offsetMs()).toBe(1_000);
  });

  it("повторная синхронизация заменяет смещение", () => {
    let local = 0;
    const clock = createServerClock(() => local);
    clock.sync("1970-01-01T00:00:10Z");
    local = 5_000;
    clock.sync("1970-01-01T00:00:06Z");
    expect(clock.offsetMs()).toBe(1_000);
  });
});

describe("msUntil", () => {
  it("считает по серверным часам, а не по локальным", () => {
    const clock = createServerClock(() => SERVER_MS - 60_000); // клиент отстаёт на минуту
    clock.sync(SERVER_TIME);
    expect(msUntil("2026-10-24T12:00:30+00:00", clock)).toBe(30_000);
    expect(msUntil("2026-10-24T11:59:00+00:00", clock)).toBe(-60_000);
  });
});
