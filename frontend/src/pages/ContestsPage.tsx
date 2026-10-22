import { useState } from "react";

import { isOrganizer } from "../api";
import { useSession } from "../features/auth";
import { ContestList, CreateContestForm } from "../features/contests";

export function ContestsPage() {
  const session = useSession();
  const [creating, setCreating] = useState(false);
  // Кнопка только у организатора; права всё равно проверяет сервер (403).
  const canCreate = session.data ? isOrganizer(session.data) : false;

  return (
    <>
      <div className="toolbar">
        <h2>Конкурсы</h2>
        {canCreate && !creating ? (
          <button
            type="button"
            className="button"
            onClick={() => {
              setCreating(true);
            }}
          >
            Создать конкурс
          </button>
        ) : null}
      </div>
      {canCreate && creating ? (
        <CreateContestForm
          onCreated={() => {
            setCreating(false);
          }}
          onCancel={() => {
            setCreating(false);
          }}
        />
      ) : null}
      <ContestList isOrganizer={canCreate} />
    </>
  );
}
