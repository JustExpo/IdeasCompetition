import type { ReactNode } from "react";

import { ApiError, describeError, type VotingIdea } from "../../api";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Notice } from "../../shared/ui/Notice";
import { useVoteMutation } from "./queries";

interface VotingListProps {
  contestId: number;
  items: readonly VotingIdea[];
  /** Кнопки голоса показываются, только если сервер разрешил действие (`allowed_actions`). */
  canVote: boolean;
  /** Действия над своей идеей (удаление): их рисует страница, фичи друг друга не импортируют. */
  renderOwnActions?: (idea: VotingIdea) => ReactNode;
}

/** Фаза голосования: идеи без авторов (П4); за свою идею кнопки голоса нет. */
export function VotingList({ contestId, items, canVote, renderOwnActions }: VotingListProps) {
  if (items.length === 0) {
    return (
      <EmptyState title="Идей нет">
        В этом конкурсе никто не предложил идей, голосовать не за что.
      </EmptyState>
    );
  }
  const nothingToVoteFor = items.every((idea) => idea.is_mine);
  return (
    <section aria-label="Идеи для голосования">
      <h3>Идеи для голосования</h3>
      {nothingToVoteFor ? (
        <Notice tone="info">Голосовать не за что: все идеи в этом конкурсе — ваши.</Notice>
      ) : null}
      <ul className="idea-list">
        {items.map((idea) => (
          <VotingItem
            key={idea.id}
            contestId={contestId}
            idea={idea}
            canVote={canVote}
            ownActions={idea.is_mine ? renderOwnActions?.(idea) : null}
          />
        ))}
      </ul>
    </section>
  );
}

interface VotingItemProps {
  contestId: number;
  idea: VotingIdea;
  canVote: boolean;
  ownActions: ReactNode;
}

function VotingItem({ contestId, idea, canVote, ownActions }: VotingItemProps) {
  const vote = useVoteMutation(contestId);
  const failure = vote.error ? describeError(vote.error) : null;
  // Идею удалил автор, пока страница была открыта: понятный текст вместо общего «не найдена».
  const deleted = vote.error instanceof ApiError && vote.error.code === "idea_not_found";
  return (
    <li className="idea-item">
      <h4>{idea.title}</h4>
      <p className="idea-description">{idea.description}</p>
      {failure ? (
        <Notice tone="error">{deleted ? "Идея удалена автором." : failure.message}</Notice>
      ) : null}
      {idea.is_mine ? (
        <>
          <p className="meta">Это ваша идея: за неё голосовать нельзя.</p>
          {ownActions}
        </>
      ) : canVote ? (
        <button
          type="button"
          className={idea.my_vote ? "button button-secondary" : "button"}
          aria-pressed={idea.my_vote}
          disabled={vote.isPending}
          onClick={() => {
            vote.mutate({ ideaId: idea.id, vote: !idea.my_vote });
          }}
        >
          {idea.my_vote ? "Отозвать голос" : "Проголосовать"}
        </button>
      ) : null}
    </li>
  );
}
