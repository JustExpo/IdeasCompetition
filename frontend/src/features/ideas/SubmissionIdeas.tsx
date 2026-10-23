import { useRef, useState } from "react";

import type { IdeaDraft, OwnIdea } from "../../api";
import { formatDateTime } from "../../shared/lib/dateTime";
import { EmptyState } from "../../shared/ui/EmptyState";
import { DeleteIdeaButton } from "./DeleteIdeaButton";
import { IdeaForm } from "./IdeaForm";
import { useEditIdea, useSubmitIdea } from "./queries";

interface SubmissionIdeasProps {
  contestId: number;
  items: readonly OwnIdea[];
  /** Форма подачи показывается, только если сервер разрешил действие (`allowed_actions`). */
  canSubmit: boolean;
}

function newRequestId(): string {
  return crypto.randomUUID();
}

/** Фаза приёма: пользователь видит только свои идеи (П3), подаёт новые и правит прежние. */
export function SubmissionIdeas({ contestId, items, canSubmit }: SubmissionIdeasProps) {
  // Ключ повтора относится к конкретному тексту: повторная отправка того же текста (второй клик,
  // повтор после обрыва сети) идёт с тем же ключом и не создаёт дубль (§8.3); если пользователь
  // изменил текст, ключ новый — иначе сервер ответил бы 422 `idempotency_key_reused`.
  const lastAttempt = useRef<{ draft: IdeaDraft; requestId: string } | null>(null);
  // После успеха форма пересоздаётся (меняется `formKey`) и поля очищаются.
  const [formKey, setFormKey] = useState(0);
  const submit = useSubmitIdea(contestId);

  const send = (draft: IdeaDraft): void => {
    const previous = lastAttempt.current;
    const sameText =
      previous !== null &&
      previous.draft.title === draft.title &&
      previous.draft.description === draft.description;
    const requestId = sameText ? previous.requestId : newRequestId();
    lastAttempt.current = { draft, requestId };
    submit.mutate(
      { draft, clientRequestId: requestId },
      {
        onSuccess: () => {
          lastAttempt.current = null;
          setFormKey((key) => key + 1);
          submit.reset();
        },
      },
    );
  };

  return (
    <section aria-label="Мои идеи">
      {canSubmit ? (
        <IdeaForm
          key={formKey}
          heading="Новая идея"
          submitLabel="Предложить идею"
          pending={submit.isPending}
          error={submit.error}
          onSubmit={send}
        />
      ) : null}
      <h3>Мои идеи</h3>
      {items.length === 0 ? (
        <EmptyState title="Вы ещё не предложили идей">
          Чужие идеи в этой фазе не показываются: они откроются на голосовании без имён авторов.
        </EmptyState>
      ) : (
        <ul className="idea-list">
          {items.map((idea) => (
            <OwnIdeaItem key={idea.id} contestId={contestId} idea={idea} canEdit={canSubmit} />
          ))}
        </ul>
      )}
    </section>
  );
}

interface OwnIdeaItemProps {
  contestId: number;
  idea: OwnIdea;
  canEdit: boolean;
}

function OwnIdeaItem({ contestId, idea, canEdit }: OwnIdeaItemProps) {
  const [editing, setEditing] = useState(false);
  const edit = useEditIdea(contestId);

  if (editing) {
    return (
      <li className="idea-item">
        <IdeaForm
          heading="Правка идеи"
          submitLabel="Сохранить"
          initial={{ title: idea.title, description: idea.description }}
          pending={edit.isPending}
          error={edit.error}
          onCancel={() => {
            edit.reset();
            setEditing(false);
          }}
          onSubmit={(draft) => {
            edit.mutate(
              { ideaId: idea.id, draft, version: idea.version },
              {
                onSuccess: () => {
                  setEditing(false);
                },
              },
            );
          }}
        />
      </li>
    );
  }
  return (
    <li className="idea-item">
      <h4>{idea.title}</h4>
      <p className="idea-description">{idea.description}</p>
      <p className="meta">Подана {formatDateTime(idea.submitted_at)}</p>
      {canEdit ? (
        <div className="toolbar">
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setEditing(true);
            }}
          >
            Править
          </button>
          <DeleteIdeaButton contestId={contestId} ideaId={idea.id} warnAboutVotes={false} />
        </div>
      ) : null}
    </li>
  );
}
