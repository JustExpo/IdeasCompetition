import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createServerClock } from "../../shared/lib/serverTime";
import { Countdown, formatRemaining } from "./Countdown";

const START = Date.parse("2026-10-24T12:00:00Z");
const iso = (offsetMs: number): string => new Date(START + offsetMs).toISOString();

describe("formatRemaining", () => {
  it("показывает старшие единицы только когда они нужны", () => {
    expect(formatRemaining(1000)).toBe("01 с");
    expect(formatRemaining(61_000)).toBe("01 мин 01 с");
    expect(formatRemaining(3_661_000)).toBe("1 ч 01 мин 01 с");
    expect(formatRemaining(90_061_000)).toBe("1 д 1 ч 01 мин 01 с");
    expect(formatRemaining(-5)).toBe("00 с");
  });
});

describe("Countdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("на d−1 с ещё приём идей, на d — уже голосование, на втором дедлайне — конец", () => {
    const clock = createServerClock();
    render(
      <Countdown submissionDeadline={iso(10_000)} votingDeadline={iso(20_000)} clock={clock} />,
    );
    expect(screen.getByText("До закрытия приёма идей: 10 с")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(9000);
    });
    expect(screen.getByText("До закрытия приёма идей: 01 с")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("До закрытия голосования: 10 с")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByText("Конкурс завершён.")).toBeInTheDocument();
  });

  it("считает по серверным часам, а не по часам компьютера", () => {
    const clock = createServerClock();
    clock.sync(iso(5000)); // сервер впереди на 5 секунд
    render(
      <Countdown submissionDeadline={iso(10_000)} votingDeadline={iso(20_000)} clock={clock} />,
    );
    expect(screen.getByText("До закрытия приёма идей: 05 с")).toBeInTheDocument();
  });
});
