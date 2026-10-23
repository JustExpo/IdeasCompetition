import { vi } from "vitest";

/**
 * Поддельный WebSocket: тест сам «присылает» сообщения сервера и закрывает соединение.
 * Нужен потому, что jsdom пытался бы подключиться к настоящему адресу.
 */
export class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  readyState: number = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
  }

  /** Сервер принял соединение. */
  serverOpens(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  serverSends(message: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  /** Сервер закрыл соединение (или оно оборвалось) с кодом `code`. */
  serverCloses(code = 1006): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close", { code }));
  }

  static get last(): FakeWebSocket {
    const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
    if (socket === undefined) {
      throw new Error("WebSocket ещё не создавался");
    }
    return socket;
  }
}

export function installFakeWebSocket(): void {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
}
