/**
 * Идентификатор сборки сервера (`X-App-Build`, приветствие WebSocket). Первое увиденное значение —
 * сборка, под которую загружен SPA; другое значение позже значит, что сервер обновили и странице
 * пора перезагрузиться (CLAUDE.md §8.1).
 */
let baseline: string | null = null;
let mismatch = false;
const listeners = new Set<() => void>();

export function observeBuild(build: string | null | undefined): void {
  if (build === null || build === undefined || build === "") {
    return;
  }
  if (baseline === null) {
    baseline = build;
    return;
  }
  if (build !== baseline && !mismatch) {
    mismatch = true;
    listeners.forEach((listener) => {
      listener();
    });
  }
}

export function isNewBuildAvailable(): boolean {
  return mismatch;
}

export function subscribeToBuildChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Только для тестов: забыть увиденную сборку. */
export function resetBuildObservation(): void {
  baseline = null;
  mismatch = false;
  e2eMode = false;
  listeners.clear();
}

/** Режим e2e сообщает заголовок `X-App-Mode` (только в тестовом стенде): SPA рисует плашку. */
let e2eMode = false;

export function observeMode(mode: string | null | undefined): void {
  if (mode === "e2e" && !e2eMode) {
    e2eMode = true;
    listeners.forEach((listener) => {
      listener();
    });
  }
}

export function isE2EMode(): boolean {
  return e2eMode;
}
