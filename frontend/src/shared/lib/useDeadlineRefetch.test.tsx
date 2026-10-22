import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createServerClock } from "./serverTime";
import { MAX_WAIT_MS, useDeadlineRefetch } from "./useDeadlineRefetch";

const START = Date.parse("2026-10-24T12:00:00Z");
const iso = (offsetMs: number): string => new Date(START + offsetMs).toISOString();

function setVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("useDeadlineRefetch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
  });
  afterEach(() => {
    vi.useRealTimers();
    setVisibility("visible");
  });

  it("вызывает колбэк, когда серверное время доходит до дедлайна", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    renderHook(() => {
      useDeadlineRefetch([iso(10_000)], onReached, clock);
    });
    vi.advanceTimersByTime(9_999);
    expect(onReached).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onReached).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(60_000);
    expect(onReached).toHaveBeenCalledTimes(1);
  });

  it("два дедлайна — два вызова", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    renderHook(() => {
      useDeadlineRefetch([iso(5_000), iso(20_000)], onReached, clock);
    });
    vi.advanceTimersByTime(5_000);
    expect(onReached).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(15_000);
    expect(onReached).toHaveBeenCalledTimes(2);
  });

  it("уже прошедший дедлайн не вызывает колбэк", () => {
    const onReached = vi.fn();
    renderHook(() => {
      useDeadlineRefetch([iso(-1_000)], onReached, createServerClock());
    });
    vi.advanceTimersByTime(120_000);
    expect(onReached).not.toHaveBeenCalled();
  });

  it("часы клиента спешат: дедлайн наступает по серверному времени", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    clock.sync(iso(-60_000)); // сервер отстаёт от компьютера на минуту
    renderHook(() => {
      useDeadlineRefetch([iso(10_000)], onReached, clock);
    });
    vi.advanceTimersByTime(69_999);
    expect(onReached).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onReached).toHaveBeenCalledTimes(1);
  });

  it("далёкий дедлайн ждётся короткими отрезками", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    const spy = vi.spyOn(window, "setTimeout");
    renderHook(() => {
      useDeadlineRefetch([iso(10 * MAX_WAIT_MS)], onReached, clock);
    });
    expect(spy).toHaveBeenCalledWith(expect.any(Function), MAX_WAIT_MS);
    vi.advanceTimersByTime(10 * MAX_WAIT_MS);
    expect(onReached).toHaveBeenCalledTimes(1);
  });

  it("фоновая вкладка: таймер не сработал, но возврат на вкладку обнаруживает дедлайн", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    renderHook(() => {
      useDeadlineRefetch([iso(10_000)], onReached, clock);
    });
    setVisibility("hidden");
    // Время ушло вперёд, но браузер таймеры не запускал (троттлинг/сон устройства).
    vi.setSystemTime(START + 3_600_000);
    expect(onReached).not.toHaveBeenCalled();
    setVisibility("visible");
    expect(onReached).toHaveBeenCalledTimes(1);
  });

  it("скрытие вкладки колбэк не вызывает", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    renderHook(() => {
      useDeadlineRefetch([iso(10_000)], onReached, clock);
    });
    setVisibility("hidden");
    expect(onReached).not.toHaveBeenCalled();
  });

  it("после размонтирования таймеры и слушатели сняты", () => {
    const onReached = vi.fn();
    const clock = createServerClock();
    const { unmount } = renderHook(() => {
      useDeadlineRefetch([iso(10_000)], onReached, clock);
    });
    unmount();
    vi.advanceTimersByTime(60_000);
    setVisibility("visible");
    expect(onReached).not.toHaveBeenCalled();
  });

  it("использует последнюю версию колбэка", () => {
    const first = vi.fn();
    const second = vi.fn();
    const clock = createServerClock();
    const { rerender } = renderHook(
      ({ callback }) => {
        useDeadlineRefetch([iso(10_000)], callback, clock);
      },
      { initialProps: { callback: first } },
    );
    rerender({ callback: second });
    vi.advanceTimersByTime(10_000);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
