/**
 * Дата и время для людей и для API. Backend принимает время только со смещением пояса
 * (CLAUDE.md §8.1), а человек вводит его в поясе своего браузера (допущение IC-016).
 */

const LOCAL_INPUT = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

function pad(value: number, length = 2): string {
  return String(value).padStart(length, "0");
}

/**
 * Значение поля `datetime-local` («2026-10-24T18:00», пояс браузера) → ISO 8601 со смещением
 * («2026-10-24T18:00:00+03:00»). `null`, если значение пустое, не существует (31 февраля) или
 * попало в «пропавший» час перехода на летнее время: такое время нельзя сохранить однозначно.
 */
export function localInputToIso(value: string): string | null {
  const match = LOCAL_INPUT.exec(value);
  if (match === null) {
    return null;
  }
  const [year, month, day, hour, minute] = match.slice(1).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  const date = new Date(year, month - 1, day, hour, minute);
  const roundTrips =
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day &&
    date.getHours() === hour &&
    date.getMinutes() === minute;
  if (!roundTrips) {
    return null;
  }
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes < 0 ? "-" : "+";
  const absolute = Math.abs(offsetMinutes);
  const offset = `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`;
  return `${pad(year, 4)}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}:00${offset}`;
}

const DISPLAY_FORMAT = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

/** Момент (ISO 8601) в поясе браузера: «24 окт. 2026 г., 18:00». */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : DISPLAY_FORMAT.format(date);
}
