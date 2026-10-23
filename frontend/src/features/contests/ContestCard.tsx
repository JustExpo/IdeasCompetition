import type { ContestDetail } from "../../api";
import { formatDateTime } from "../../shared/lib/dateTime";
import { Countdown } from "./Countdown";
import { phaseLabel } from "./phase";

/** Шапка страницы конкурса: тема, фаза, дедлайны, таймер и правило ничьей (П10). */
export function ContestCard({ contest }: { contest: ContestDetail }) {
  return (
    <section className="card" aria-label="Конкурс">
      <h2>{contest.topic}</h2>
      <p>
        <span className="badge">{phaseLabel(contest.phase)}</span>
      </p>
      {contest.description === "" ? null : (
        <p className="idea-description">{contest.description}</p>
      )}
      <p className="meta">
        Приём идей до {formatDateTime(contest.submission_deadline)} · голосование до{" "}
        {formatDateTime(contest.voting_deadline)}
      </p>
      <Countdown
        submissionDeadline={contest.submission_deadline}
        votingDeadline={contest.voting_deadline}
      />
      <p className="meta">Правило ничьей: {contest.tie_break_rule}</p>
    </section>
  );
}
