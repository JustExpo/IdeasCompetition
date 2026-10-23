import { observeBuild } from "./build";

/** Сообщения сервера по WebSocket: только сигналы «перечитай», данных в них нет (Р8). */
export type ContestEventType = "ideas_changed" | "idea_deleted" | "results_changed";

export interface ContestEvent {
  type: ContestEventType;
  contestId: number;
  ideaId?: string;
}

export type ConnectionStatus = "connecting" | "open" | "offline";

export interface ContestEventHandlers {
  onEvent: (event: ContestEvent) => void;
  onStatus: (status: ConnectionStatus) => void;
  /** Соединение восстановлено после обрыва: события за разрыв потеряны, нужно перечитать всё. */
  onResync: () => void;
  /** Сервер закрыл соединение: сессия отозвана (выход в другой вкладке, отзыв оператором). */
  onSessionEnded: () => void;
}

export interface ContestEventsOptions {
  /** Задержки переподключения; в тестах подменяются на короткие. */
  retryDelaysMs?: readonly number[];
  pingIntervalMs?: number;
}

const DEFAULT_RETRY_DELAYS_MS = [500, 1000, 2000, 4000, 8000, 15000] as const;
const DEFAULT_PING_INTERVAL_MS = 25_000;
const CLOSE_NOT_AUTHENTICATED = 4401;

const EVENT_TYPES: readonly string[] = ["ideas_changed", "idea_deleted", "results_changed"];

interface WireMessage {
  v?: unknown;
  type?: unknown;
  contest_id?: unknown;
  idea_id?: unknown;
  build?: unknown;
}

function socketUrl(contestId: number): string {
  const url = new URL(`/api/contests/${String(contestId)}/events`, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function parseMessage(data: unknown): WireMessage | null {
  if (typeof data !== "string") {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(data);
    return typeof parsed === "object" && parsed !== null ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * Подписка на события конкурса. Переподключается сама с нарастающей паузой; после каждого
 * восстановления просит перечитать данные, потому что сигналы за разрыв не повторяются.
 * Возвращает функцию отключения.
 */
export function connectContestEvents(
  contestId: number,
  handlers: ContestEventHandlers,
  options: ContestEventsOptions = {},
): () => void {
  const retryDelays = options.retryDelaysMs ?? DEFAULT_RETRY_DELAYS_MS;
  const pingIntervalMs = options.pingIntervalMs ?? DEFAULT_PING_INTERVAL_MS;
  let socket: WebSocket | null = null;
  let stopped = false;
  let everOpened = false;
  let attempt = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let pingTimer: ReturnType<typeof setInterval> | undefined;

  const clearTimers = () => {
    clearTimeout(retryTimer);
    clearInterval(pingTimer);
    retryTimer = undefined;
    pingTimer = undefined;
  };

  const scheduleReconnect = () => {
    if (stopped) {
      return;
    }
    const delay = retryDelays[Math.min(attempt, retryDelays.length - 1)] ?? 1000;
    attempt += 1;
    retryTimer = setTimeout(open, delay);
  };

  function open() {
    if (stopped) {
      return;
    }
    handlers.onStatus("connecting");
    const ws = new WebSocket(socketUrl(contestId));
    socket = ws;

    ws.onopen = () => {
      attempt = 0;
      handlers.onStatus("open");
      if (everOpened) {
        handlers.onResync();
      }
      everOpened = true;
      pingIntervalCleanup();
      pingTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, pingIntervalMs);
    };

    ws.onmessage = (message: MessageEvent) => {
      const wire = parseMessage(message.data);
      if (wire === null) {
        return;
      }
      if (wire.type === "hello") {
        observeBuild(typeof wire.build === "string" ? wire.build : null);
        return;
      }
      if (
        typeof wire.type === "string" &&
        EVENT_TYPES.includes(wire.type) &&
        typeof wire.contest_id === "number"
      ) {
        handlers.onEvent({
          type: wire.type as ContestEventType,
          contestId: wire.contest_id,
          ...(typeof wire.idea_id === "string" ? { ideaId: wire.idea_id } : {}),
        });
      }
    };

    ws.onclose = (closeEvent: CloseEvent) => {
      pingIntervalCleanup();
      if (socket === ws) {
        socket = null;
      }
      if (stopped) {
        return;
      }
      if (closeEvent.code === CLOSE_NOT_AUTHENTICATED) {
        handlers.onStatus("offline");
        handlers.onSessionEnded();
        return;
      }
      handlers.onStatus("offline");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // Подробности ошибки сети недоступны; переподключением займётся `onclose`.
    };
  }

  function pingIntervalCleanup() {
    clearInterval(pingTimer);
    pingTimer = undefined;
  }

  // Фоновая вкладка может долго не получать таймеры: при возвращении подключаемся сразу.
  const onVisibility = () => {
    if (document.visibilityState === "visible" && socket === null && !stopped) {
      clearTimeout(retryTimer);
      attempt = 0;
      open();
    }
  };
  document.addEventListener("visibilitychange", onVisibility);

  open();

  return () => {
    stopped = true;
    document.removeEventListener("visibilitychange", onVisibility);
    clearTimers();
    socket?.close();
    socket = null;
  };
}
