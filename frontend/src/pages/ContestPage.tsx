import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { describeError, isOrganizer, type ContestDetail } from "../api";
import { useSession } from "../features/auth";
import { ContestCard, useContest } from "../features/contests";
import { DeleteIdeaButton, SubmissionIdeas, useIdeasListing } from "../features/ideas";
import { DashboardPanel } from "../features/organizer";
import { ResultsTable } from "../features/results";
import { VotingList } from "../features/voting";
import { contestScope } from "../shared/lib/queryKeys";
import { useDeadlineRefetch } from "../shared/lib/useDeadlineRefetch";
import { EmptyState } from "../shared/ui/EmptyState";
import { Notice } from "../shared/ui/Notice";
import { NotFoundPage } from "./NotFoundPage";

function parseContestId(value: string | undefined): number | null {
  return value !== undefined && /^\d{1,15}$/.test(value) ? Number(value) : null;
}

export function ContestPage() {
  const contestId = parseContestId(useParams().contestId);
  if (contestId === null) {
    return <NotFoundPage />;
  }
  return <ContestScreen contestId={contestId} />;
}

function ContestScreen({ contestId }: { contestId: number }) {
  const session = useSession();
  const contest = useContest(contestId);
  const queryClient = useQueryClient();
  // В момент дедлайна (по серверному времени) перечитываем всё: экран сам переходит к
  // следующей фазе, даже если страница открыта. Запоздавшую запись всё равно отклонит сервер.
  useDeadlineRefetch(
    contest.data ? [contest.data.submission_deadline, contest.data.voting_deadline] : [],
    () => {
      void queryClient.invalidateQueries({ queryKey: contestScope(contestId) });
    },
  );

  if (contest.isPending || session.isPending) {
    return <p role="status">Загрузка конкурса…</p>;
  }
  if (contest.isError) {
    const failure = describeError(contest.error);
    if (failure.kind === "not_found") {
      return (
        <EmptyState title="Конкурс не найден">
          <Link to="/">К списку конкурсов</Link>
        </EmptyState>
      );
    }
    return (
      <Notice tone="error" onRetry={() => void contest.refetch()}>
        {failure.message}
      </Notice>
    );
  }
  const organizer = session.data ? isOrganizer(session.data) : false;
  return (
    <>
      <p>
        <Link to="/">← Все конкурсы</Link>
      </p>
      <ContestCard contest={contest.data} />
      {organizer ? (
        <OrganizerBody contestId={contestId} contest={contest.data} />
      ) : (
        <EmployeeBody contestId={contestId} contest={contest.data} />
      )}
    </>
  );
}

function OrganizerBody({ contestId, contest }: { contestId: number; contest: ContestDetail }) {
  const finished = contest.phase === "finished";
  return (
    <>
      <DashboardPanel contestId={contestId} live={!finished} />
      {finished ? <ResultsTable contestId={contestId} /> : null}
    </>
  );
}

function EmployeeBody({ contestId, contest }: { contestId: number; contest: ContestDetail }) {
  const ideas = useIdeasListing(contestId);
  if (ideas.isPending) {
    return <p role="status">Загрузка идей…</p>;
  }
  if (ideas.isError) {
    return (
      <Notice tone="error" onRetry={() => void ideas.refetch()}>
        {describeError(ideas.error).message}
      </Notice>
    );
  }
  // Кнопки определяет сервер (`allowed_actions`), фронт фазовых правил не дублирует.
  const listing = ideas.data;
  switch (listing.phase) {
    case "submission":
      return (
        <SubmissionIdeas
          contestId={contestId}
          items={listing.items}
          canSubmit={contest.allowed_actions.includes("submit_idea")}
        />
      );
    case "voting":
      return (
        <VotingList
          contestId={contestId}
          items={listing.items}
          canVote={contest.allowed_actions.includes("vote")}
          renderOwnActions={(idea) => (
            <DeleteIdeaButton contestId={contestId} ideaId={idea.id} warnAboutVotes />
          )}
        />
      );
    case "finished":
      return <ResultsTable contestId={contestId} />;
  }
}
