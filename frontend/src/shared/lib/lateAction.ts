import { useSyncExternalStore } from "react";

/**
 * Сообщение о том, что действие опоздало к дедлайну (П2). После такой ошибки экран сразу
 * переходит к следующей фазе и форма с локальной ошибкой исчезает, поэтому текст держим здесь,
 * а страница конкурса показывает его над содержимым, пока человек не закроет его или не уйдёт.
 */
let message: string | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((listener) => {
    listener();
  });
}

export function reportLateAction(text: string): void {
  message = text;
  emit();
}

export function clearLateAction(): void {
  if (message !== null) {
    message = null;
    emit();
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useLateAction(): string | null {
  return useSyncExternalStore(subscribe, () => message);
}
