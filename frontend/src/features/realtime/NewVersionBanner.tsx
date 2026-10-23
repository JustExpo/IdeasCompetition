import { useSyncExternalStore } from "react";

import { isNewBuildAvailable, subscribeToBuildChange } from "../../api";
import { Notice } from "../../shared/ui/Notice";

/** Сервер обновили, пока страница была открыта: старый интерфейс может не совпадать с API. */
export function NewVersionBanner() {
  const available = useSyncExternalStore(subscribeToBuildChange, isNewBuildAvailable);
  if (!available) {
    return null;
  }
  return (
    <Notice tone="info">
      Доступна новая версия приложения.{" "}
      <button
        type="button"
        className="button button-secondary"
        onClick={() => {
          window.location.reload();
        }}
      >
        Обновить страницу
      </button>
    </Notice>
  );
}
