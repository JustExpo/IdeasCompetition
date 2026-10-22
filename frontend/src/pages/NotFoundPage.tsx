import { Link } from "react-router-dom";

import { EmptyState } from "../shared/ui/EmptyState";

export function NotFoundPage() {
  return (
    <main className="page">
      <EmptyState title="Страница не найдена">
        Проверьте адрес или вернитесь <Link to="/">к списку конкурсов</Link>.
      </EmptyState>
    </main>
  );
}
