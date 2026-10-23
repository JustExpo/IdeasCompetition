import { describeError, type Dashboard } from "../../api";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Notice } from "../../shared/ui/Notice";
import { useDashboard } from "./queries";

interface DashboardPanelProps {
  contestId: number;
  /** Конкурс ещё не завершён: цифры меняются, поэтому панель опрашивает сервер. */
  live: boolean;
}

/** Экран организатора (Ф5): число идей, число проголосовавших и текущие места без авторов. */
export function DashboardPanel({ contestId, live }: DashboardPanelProps) {
  const dashboard = useDashboard(contestId, live);
  if (dashboard.isPending) {
    return <p role="status">Загрузка данных конкурса…</p>;
  }
  if (dashboard.isError && dashboard.data === undefined) {
    return (
      <Notice tone="error" onRetry={() => void dashboard.refetch()}>
        {describeError(dashboard.error).message}
      </Notice>
    );
  }
  return (
    <section aria-label="Экран организатора">
      <h3>Ход конкурса</h3>
      {dashboard.isError ? (
        // Последние цифры остаются на экране: пропавшая связь не должна стирать картину.
        <Notice tone="error">
          Нет связи с сервером: показаны последние полученные данные. Обновление продолжится само.
        </Notice>
      ) : null}
      <DashboardView dashboard={dashboard.data} />
    </section>
  );
}

export function DashboardView({ dashboard }: { dashboard: Dashboard }) {
  return (
    <>
      <dl className="stats">
        <div>
          <dt>Идей подано</dt>
          <dd>{dashboard.ideas_count}</dd>
        </div>
        <div>
          <dt>Проголосовало</dt>
          <dd>{dashboard.voters_count}</dd>
        </div>
      </dl>
      {dashboard.results.length === 0 ? (
        <EmptyState title="Идей пока нет">
          Результаты появятся, когда сотрудники предложат идеи.
        </EmptyState>
      ) : (
        <table className="results" aria-label="Текущие результаты">
          <thead>
            <tr>
              <th scope="col">Место</th>
              <th scope="col">Идея</th>
              <th scope="col">Голоса</th>
            </tr>
          </thead>
          <tbody>
            {dashboard.results.map((item) => (
              <tr key={item.idea_id}>
                <td>{item.place}</td>
                <td>{item.title}</td>
                <td>{item.votes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
