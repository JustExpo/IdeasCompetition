import { useState } from "react";

import { describeError } from "../../api";
import { Notice } from "../../shared/ui/Notice";
import { useDeleteIdea } from "./queries";

interface DeleteIdeaButtonProps {
  contestId: number;
  ideaId: string;
  /** Идея уже собрала голоса: подтверждение предупреждает, что они пропадут (П11). */
  warnAboutVotes: boolean;
}

/** Удаление своей идеи с подтверждением: действие необратимо, окно `confirm` блокирует вкладку. */
export function DeleteIdeaButton({ contestId, ideaId, warnAboutVotes }: DeleteIdeaButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const remove = useDeleteIdea(contestId);

  if (!confirming) {
    return (
      <button
        type="button"
        className="button button-secondary"
        onClick={() => {
          setConfirming(true);
        }}
      >
        Удалить
      </button>
    );
  }
  return (
    <div className="confirm" role="group" aria-label="Подтверждение удаления">
      <p>
        Удалить идею?
        {warnAboutVotes ? " Голоса за неё тоже будут удалены." : ""}
      </p>
      {remove.isError ? <Notice tone="error">{describeError(remove.error).message}</Notice> : null}
      <div className="toolbar">
        <button
          type="button"
          className="button button-danger"
          disabled={remove.isPending}
          onClick={() => {
            remove.mutate(ideaId);
          }}
        >
          {remove.isPending ? "Удаляем…" : "Да, удалить"}
        </button>
        <button
          type="button"
          className="button button-secondary"
          onClick={() => {
            setConfirming(false);
          }}
        >
          Нет
        </button>
      </div>
    </div>
  );
}
