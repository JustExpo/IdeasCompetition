import { useState } from "react";
import { Link } from "react-router-dom";

import { CONTESTS_PAGE_SIZE, describeError } from "../../api";
import { formatDateTime } from "../../shared/lib/dateTime";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Notice } from "../../shared/ui/Notice";
import { phaseLabel } from "./phase";
import { useContests } from "./queries";

interface ContestListProps {
  /** Организатору при пустом списке подсказываем создать конкурс. */
  isOrganizer: boolean;
}

export function ContestList({ isOrganizer }: ContestListProps) {
  const [offset, setOffset] = useState(0);
  const contests = useContests(offset);

  if (contests.isPending) {
    return <p role="status">Загрузка конкурсов…</p>;
  }
  if (contests.isError) {
    return (
      <Notice tone="error" onRetry={() => void contests.refetch()}>
        {describeError(contests.error).message}
      </Notice>
    );
  }

  const { items, total } = contests.data;
  if (total === 0) {
    return (
      <EmptyState title="Пока нет конкурсов">
        {isOrganizer
          ? "Создайте первый конкурс, и сотрудники смогут подавать идеи."
          : "Когда организатор создаст конкурс, он появится здесь."}
      </EmptyState>
    );
  }
  if (items.length === 0) {
    // Страница за концом списка (например, конкурсы удалили): возвращаем на первую.
    return (
      <EmptyState title="На этой странице конкурсов нет">
        <button
          type="button"
          className="button button-secondary"
          onClick={() => {
            setOffset(0);
          }}
        >
          К началу списка
        </button>
      </EmptyState>
    );
  }

  const hasPrevious = offset > 0;
  const hasNext = offset + CONTESTS_PAGE_SIZE < total;
  return (
    <>
      <ul className="contest-list" aria-label="Конкурсы">
        {items.map((contest) => (
          <li key={contest.id} className="contest-item">
            <Link to={`/contests/${String(contest.id)}`}>{contest.topic}</Link>
            <span className="badge">{phaseLabel(contest.phase)}</span>
            <p className="meta">
              Приём идей до {formatDateTime(contest.submission_deadline)} · голосование до{" "}
              {formatDateTime(contest.voting_deadline)}
            </p>
          </li>
        ))}
      </ul>
      {hasPrevious || hasNext ? (
        <nav className="pager" aria-label="Страницы списка">
          <button
            type="button"
            className="button button-secondary"
            disabled={!hasPrevious}
            onClick={() => {
              setOffset(Math.max(0, offset - CONTESTS_PAGE_SIZE));
            }}
          >
            Назад
          </button>
          <span>
            {offset + 1}–{offset + items.length} из {total}
          </span>
          <button
            type="button"
            className="button button-secondary"
            disabled={!hasNext}
            onClick={() => {
              setOffset(offset + CONTESTS_PAGE_SIZE);
            }}
          >
            Вперёд
          </button>
        </nav>
      ) : null}
    </>
  );
}
