import { describe, expect, it } from "vitest";

import { countCodePoints } from "./codePoints";

describe("countCodePoints", () => {
  it("считает эмодзи одной кодовой точкой, а не двумя единицами UTF-16", () => {
    expect(countCodePoints("😀")).toBe(1);
    expect("😀".length).toBe(2);
    expect(countCodePoints("😀".repeat(200))).toBe(200);
    expect(countCodePoints("😀".repeat(201))).toBe(201);
  });

  it("нормализует NFC и обрезает пробелы по краям", () => {
    expect(countCodePoints("é")).toBe(1); // e + акцент → é
    expect(countCodePoints("  идея \n")).toBe(4);
    expect(countCodePoints("   ")).toBe(0);
  });
});
