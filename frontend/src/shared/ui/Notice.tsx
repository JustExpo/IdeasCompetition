import type { ReactNode } from "react";

interface NoticeProps {
  tone: "error" | "info";
  children: ReactNode;
  /** Кнопка повтора для временных сбоев. */
  onRetry?: () => void;
}

/** Сообщение пользователю. Ошибки объявляются скринридеру сразу (`role="alert"`). */
export function Notice({ tone, children, onRetry }: NoticeProps) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <p>{children}</p>
      {onRetry ? (
        <button type="button" className="button button-secondary" onClick={onRetry}>
          Повторить
        </button>
      ) : null}
    </div>
  );
}
