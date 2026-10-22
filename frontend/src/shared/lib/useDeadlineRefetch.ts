import { useEffect, useRef } from "react";

import { serverClock, type ServerClock } from "./serverTime";

/**
 * Самый длинный отрезок ожидания. Таймеры фоновой вкладки браузер замедляет и может задержать,
 * а `setTimeout` не умеет ждать дольше ~24 суток; поэтому ждём короткими отрезками и каждый раз
 * сверяемся с серверными часами, а не доверяем одному длинному таймеру.
 */
export const MAX_WAIT_MS = 30_000;

/**
 * Вызывает `onReached`, когда серверное время пересекает любой из дедлайнов (ISO 8601).
 * Проверка идёт по таймеру и сразу при возвращении на вкладку (`visibilitychange`), поэтому
 * дедлайн, прошедший в фоне, обнаруживается без ожидания таймера. Дедлайны, уже прошедшие
 * к моменту монтирования, не вызывают `onReached`: данные и так свежие.
 */
export function useDeadlineRefetch(
  deadlines: readonly string[],
  onReached: () => void,
  clock: ServerClock = serverClock,
): void {
  const callback = useRef(onReached);
  useEffect(() => {
    callback.current = onReached;
  }, [onReached]);

  // Ключ вместо массива: родитель каждый раз создаёт новый массив с теми же датами.
  const key = deadlines.join("|");

  useEffect(() => {
    const targets = key
      .split("|")
      .map((item) => Date.parse(item))
      .filter((ms) => !Number.isNaN(ms))
      .sort((a, b) => a - b);
    let checkedAt = clock.now();
    let timer: number | undefined;

    const check = (): void => {
      window.clearTimeout(timer);
      const now = clock.now();
      const crossed = targets.some((target) => target > checkedAt && target <= now);
      checkedAt = now;
      if (crossed) {
        callback.current();
      }
      const next = targets.find((target) => target > now);
      if (next !== undefined) {
        timer = window.setTimeout(check, Math.min(next - now, MAX_WAIT_MS));
      }
    };
    const onVisibility = (): void => {
      if (document.visibilityState === "visible") {
        check();
      }
    };

    check();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [key, clock]);
}
