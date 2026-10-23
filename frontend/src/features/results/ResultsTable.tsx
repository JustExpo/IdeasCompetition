import { describeError, type ContestResults } from "../../api";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Notice } from "../../shared/ui/Notice";
import { useResults } from "./queries";

interface ResultsTableProps {
  contestId: number;
}

/** Итоги конкурса: места и голоса, а после финала — авторы (Ф4, П8). */
export function ResultsTable({ contestId }: ResultsTableProps) {
  const results = useResults(contestId, true);
  if (results.isPending) {
    return <p role="status">Загрузка итогов…</p>;
  }
  if (results.isError) {
    return (
      <Notice tone="error" onRetry={() => void results.refetch()}>
        {describeError(results.error).message}
      </Notice>
    );
  }
  return <ResultsView results={results.data} />;
}

interface ResultsViewProps {
  results: ContestResults;
}

/** Таблица итогов; тип ответа (`status`) определяет, есть ли колонка авторов. */
export function ResultsView({ results }: ResultsViewProps) {
  if (results.results.length === 0) {
    return <EmptyState title="Идей нет">В конкурсе не было ни одной идеи.</EmptyState>;
  }
  switch (results.status) {
    case "final":
      return (
        <section aria-label="Итоги конкурса">
          <h3>Итоги конкурса</h3>
          <table className="results">
            <thead>
              <tr>
                <th scope="col">Место</th>
                <th scope="col">Идея</th>
                <th scope="col">Автор</th>
                <th scope="col">Голоса</th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((item) => (
                <tr key={item.idea_id} className={item.place === 1 ? "winner" : undefined}>
                  <td>{item.place}</td>
                  <td>{item.title}</td>
                  <td>{item.author_name}</td>
                  <td>{item.votes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      );
    case "in_progress":
      return (
        <section aria-label="Текущие результаты">
          <h3>Текущие результаты</h3>
          <table className="results">
            <thead>
              <tr>
                <th scope="col">Место</th>
                <th scope="col">Идея</th>
                <th scope="col">Голоса</th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((item) => (
                <tr key={item.idea_id}>
                  <td>{item.place}</td>
                  <td>{item.title}</td>
                  <td>{item.votes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      );
  }
}
