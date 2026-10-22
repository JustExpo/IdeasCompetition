import { describe, expect, it } from "vitest";

import { formatDateTime, localInputToIso } from "./dateTime";

// Пояс теста — Europe/Moscow (UTC+3, без перехода на летнее время), см. src/test/setup.ts.
describe("localInputToIso", () => {
  it("значение поля → ISO со смещением пояса браузера", () => {
    expect(localInputToIso("2026-10-24T18:00")).toBe("2026-10-24T18:00:00+03:00");
  });

  it("результат указывает на тот же момент, что и локальное время", () => {
    const iso = localInputToIso("2026-01-05T09:30");
    expect(iso).not.toBeNull();
    expect(new Date(iso ?? "").getTime()).toBe(new Date(2026, 0, 5, 9, 30).getTime());
  });

  it.each(["", "2026-10-24", "2026-10-24 18:00", "2026-10-24T18:00:00", "завтра"])(
    "неверный формат %j → null",
    (value) => {
      expect(localInputToIso(value)).toBeNull();
    },
  );

  it.each(["2026-02-31T10:00", "2026-13-01T10:00", "2026-10-24T25:00", "2026-10-24T10:61"])(
    "несуществующее время %s → null",
    (value) => {
      expect(localInputToIso(value)).toBeNull();
    },
  );
});

describe("formatDateTime", () => {
  it("показывает момент в поясе браузера", () => {
    expect(formatDateTime("2026-10-24T15:00:00+00:00")).toContain("18:00");
  });

  it("неразбираемая строка возвращается как есть", () => {
    expect(formatDateTime("не дата")).toBe("не дата");
  });
});
