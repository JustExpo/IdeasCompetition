/**
 * Единый разбор ошибок API (CLAUDE.md §8.1): `application/problem+json` → `ApiError`,
 * стабильный `code` → русский текст. Ветвиться по тексту `title` нельзя: интерфейс опирается
 * только на `code` и статус.
 */

export type ErrorKind =
  | "unauthenticated" // 401
  | "forbidden" // 403
  | "not_found" // 404
  | "conflict" // 409
  | "validation" // 400, 413, 415, 422
  | "rate_limited" // 429
  | "unavailable" // 503
  | "server" // остальные 5xx
  | "network" // ответа нет: обрыв, таймаут, сервер недоступен
  | "unknown";

export interface FieldError {
  /** Путь к полю в теле запроса: `topic`, `submission_deadline`. */
  field: string;
  /** Тип ошибки валидации (например, `string_too_short`). */
  code: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly fieldErrors: readonly FieldError[];
  readonly retryAfterSeconds: number | null;

  constructor(init: {
    status: number;
    code: string;
    title: string;
    requestId: string | null;
    fieldErrors?: readonly FieldError[];
    retryAfterSeconds?: number | null;
  }) {
    super(init.title);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId;
    this.fieldErrors = init.fieldErrors ?? [];
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }

  get kind(): ErrorKind {
    return kindOfStatus(this.status);
  }
}

export function kindOfStatus(status: number): ErrorKind {
  switch (status) {
    case 401:
      return "unauthenticated";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 409:
      return "conflict";
    case 400:
    case 413:
    case 415:
    case 422:
      return "validation";
    case 429:
      return "rate_limited";
    case 503:
      return "unavailable";
    default:
      return status >= 500 ? "server" : "unknown";
  }
}

/** Тексты для кодов сервера (CLAUDE.md §8.1, §8.2). Новый код сервера — новая строка здесь. */
const MESSAGES = {
  // Вход и регистрация
  not_authenticated: "Войдите, чтобы продолжить.",
  invalid_credentials: "Неверный e-mail или пароль.",
  too_many_attempts: "Слишком много попыток.",
  email_taken: "Этот e-mail уже зарегистрирован.",
  email_domain_not_allowed: "Регистрация доступна только с корпоративным e-mail.",
  invalid_email: "Введите корректный e-mail.",
  invalid_name: "Введите имя длиной до 100 символов.",
  invalid_password: "Пароль должен быть длиной от 10 до 128 символов.",
  // Права
  forbidden: "Недостаточно прав для этого действия.",
  organizer_cannot_participate: "Организатор не подаёт идеи и не голосует.",
  // Конкурсы
  contest_not_found: "Конкурс не найден.",
  deadlines_order: "Голосование должно закрываться позже, чем приём идей.",
  deadline_in_past: "Срок приёма идей уже прошёл: выберите время в будущем.",
  invalid_contest: "Проверьте тему и описание конкурса.",
  // Идеи и голоса (используются экранами IC-017…IC-019)
  idea_not_found: "Идея не найдена.",
  invalid_idea: "Проверьте название и описание идеи.",
  submission_closed: "Приём идей закрыт.",
  voting_closed: "Голосование закрыто.",
  idea_locked: "Идею уже нельзя изменить или удалить.",
  stale_version: "Идею изменили в другом окне. Обновите страницу и повторите.",
  idea_limit_reached: "Достигнут лимит ваших идей в этом конкурсе.",
  contest_full: "В конкурсе набрано максимальное число идей.",
  idempotency_key_reused: "Запрос повторён с другими данными. Обновите страницу.",
  own_idea_vote: "За свою идею голосовать нельзя.",
  results_not_published: "Результаты станут доступны после завершения конкурса.",
  // Общие
  validation_error: "Проверьте введённые данные.",
  invalid_json: "Запрос повреждён. Обновите страницу и повторите.",
  unsupported_media_type: "Запрос повреждён. Обновите страницу и повторите.",
  payload_too_large: "Слишком большой запрос: сократите текст.",
  origin_not_allowed: "Запрос отклонён. Откройте сайт по основному адресу.",
  not_found: "Не найдено.",
  method_not_allowed: "Действие не поддерживается.",
  service_unavailable: "Сервис временно недоступен. Повторите через несколько секунд.",
  internal_error: "Внутренняя ошибка. Попробуйте позже.",
} as const;

type KnownCode = keyof typeof MESSAGES;

function isKnownCode(code: string): code is KnownCode {
  return Object.hasOwn(MESSAGES, code);
}

/** Какое поле формы объясняет код, если сервер не указал поле в `errors[]`. */
const FIELD_BY_CODE: Readonly<Record<string, string>> = {
  email_taken: "email",
  email_domain_not_allowed: "email",
  invalid_email: "email",
  invalid_name: "name",
  invalid_password: "password",
  deadlines_order: "voting_deadline",
  deadline_in_past: "submission_deadline",
  invalid_contest: "topic",
};

const VALIDATION_TYPE_MESSAGES: Readonly<Record<string, string>> = {
  missing: "Заполните поле.",
  string_too_short: "Слишком короткое значение.",
  string_too_long: "Слишком длинное значение.",
  datetime_from_date_parsing: "Укажите дату и время.",
  timezone_aware: "Укажите дату и время вместе с часовым поясом.",
};

export interface ErrorDescription {
  kind: ErrorKind;
  /** Готовый текст для пользователя. */
  message: string;
  /** Идентификатор запроса для обращения в поддержку (есть, когда сервер ответил). */
  requestId: string | null;
  /** Сколько ждать до повтора (429, 503), если сервер сообщил. */
  retryAfterSeconds: number | null;
  /** Ошибки по полям формы: `поле → текст`. */
  fieldErrors: Readonly<Record<string, string>>;
}

export function formatWait(seconds: number): string {
  const whole = Math.max(1, Math.ceil(seconds));
  if (whole < 60) {
    return `${String(whole)} с`;
  }
  return `${String(Math.ceil(whole / 60))} мин`;
}

function withRequestId(text: string, requestId: string | null): string {
  return requestId === null ? text : `${text} Код запроса: ${requestId}.`;
}

function describeApiError(error: ApiError): ErrorDescription {
  const known = isKnownCode(error.code);
  let message: string;
  if (known) {
    message = MESSAGES[error.code];
    // По 500 нечего исправить пользователю, но код запроса помогает найти запись в логе.
    if (error.kind === "server") {
      message = withRequestId(message, error.requestId);
    }
  } else {
    message = withRequestId("Не удалось выполнить действие.", error.requestId);
  }
  if (
    error.retryAfterSeconds !== null &&
    (error.kind === "rate_limited" || error.kind === "unavailable")
  ) {
    message = `${message} Повторите через ${formatWait(error.retryAfterSeconds)}.`;
  }

  const fieldErrors: Record<string, string> = {};
  for (const item of error.fieldErrors) {
    fieldErrors[item.field] ??= VALIDATION_TYPE_MESSAGES[item.code] ?? MESSAGES.validation_error;
  }
  const codeField = FIELD_BY_CODE[error.code];
  if (codeField !== undefined && known) {
    fieldErrors[codeField] = MESSAGES[error.code];
  }

  return {
    kind: error.kind,
    message,
    requestId: error.requestId,
    retryAfterSeconds: error.retryAfterSeconds,
    fieldErrors,
  };
}

/** Описание любой ошибки, дошедшей до интерфейса: ответ сервера, обрыв сети, баг. */
export function describeError(error: unknown): ErrorDescription {
  if (error instanceof ApiError) {
    return describeApiError(error);
  }
  if (error instanceof TypeError) {
    // fetch отвечает TypeError, когда ответа нет вовсе.
    return {
      kind: "network",
      message: "Нет связи с сервером. Проверьте подключение и повторите.",
      requestId: null,
      retryAfterSeconds: null,
      fieldErrors: {},
    };
  }
  return {
    kind: "unknown",
    message: "Что-то пошло не так. Обновите страницу и повторите.",
    requestId: null,
    retryAfterSeconds: null,
    fieldErrors: {},
  };
}

/** Повторять можно только запросы чтения и только при сбое сервера или сети, не при 4xx (§8.3). */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status >= 500;
  }
  return error instanceof TypeError;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseFieldErrors(value: unknown): FieldError[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const result: FieldError[] = [];
  for (const item of value as unknown[]) {
    if (isRecord(item) && typeof item.field === "string" && typeof item.code === "string") {
      result.push({ field: item.field, code: item.code });
    }
  }
  return result;
}

function parseRetryAfter(header: string | null): number | null {
  if (header === null || !/^\d{1,7}$/.test(header.trim())) {
    return null; // формат HTTP-даты сервер не использует
  }
  return Number(header);
}

/** Собрать `ApiError` из ответа с неуспешным статусом; тело может быть любым (в т.ч. не JSON). */
export function createApiError(response: Response, body: unknown): ApiError {
  const problem = isRecord(body) ? body : {};
  const requestId =
    typeof problem.request_id === "string"
      ? problem.request_id
      : response.headers.get("X-Request-ID");
  return new ApiError({
    status: response.status,
    code: typeof problem.code === "string" ? problem.code : "unknown_error",
    title: typeof problem.title === "string" ? problem.title : response.statusText,
    requestId,
    fieldErrors: parseFieldErrors(problem.errors),
    retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")),
  });
}
