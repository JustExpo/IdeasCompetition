/**
 * Серверные часы клиента (CLAUDE.md §4.2: `Date.now()` — только здесь).
 *
 * Фазу конкурса определяет сервер, но интерфейсу нужно знать, когда перечитать данные.
 * Часы компьютера пользователя могут уходить вперёд или назад, поэтому момент дедлайна
 * считается по серверному времени: `sync` запоминает смещение «сервер − локальные часы»
 * по полю `server_time` из ответа API. Задержка сети в смещение не входит (доли секунды):
 * лишь бы страница перечитала данные рядом с дедлайном, а запоздавшую запись всё равно
 * отклонит сервер.
 */

export interface ServerClock {
  /** Текущее серверное время, мс с начала эпохи. */
  now(): number;
  /** Запомнить серверное время из ответа API (ISO 8601 со смещением). `false` — не разобрано. */
  sync(serverTime: string): boolean;
  /** Текущее смещение «сервер − локальные часы», мс. */
  offsetMs(): number;
}

export function createServerClock(readLocalMs: () => number = () => Date.now()): ServerClock {
  let offset = 0;
  return {
    now: () => readLocalMs() + offset,
    sync(serverTime) {
      const serverMs = Date.parse(serverTime);
      if (Number.isNaN(serverMs)) {
        return false;
      }
      offset = serverMs - readLocalMs();
      return true;
    },
    offsetMs: () => offset,
  };
}

/** Часы приложения: единый экземпляр, чтобы смещение знали все экраны. */
export const serverClock: ServerClock = createServerClock();

/** Сколько миллисекунд осталось до момента `deadline` (ISO); отрицательное — уже прошёл. */
export function msUntil(deadline: string, clock: ServerClock = serverClock): number {
  return Date.parse(deadline) - clock.now();
}
