import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  children?: ReactNode;
}

/** Пустое состояние списка: объясняет, почему пусто и что делать дальше. */
export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      {children ? <p>{children}</p> : null}
    </div>
  );
}
