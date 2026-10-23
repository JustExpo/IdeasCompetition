import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { connectContestEvents, type ConnectionStatus, type ContestEvent } from "../../api";
import { contestScope, dashboardKey, ideasKey, resultsKey } from "../../shared/lib/queryKeys";

interface Options {
  /** Сессия закончилась (выход в другой вкладке, отзыв): экран должен вернуть на вход. */
  onSessionEnded?: () => void;
}

/**
 * Держит WebSocket конкурса и по сигналам «перечитай» сбрасывает нужные запросы. Сервер шлёт
 * сигнал только тем, кому изменение видно по правам, а данные клиент получает обычным REST.
 */
export function useContestEvents(contestId: number, options: Options = {}): ConnectionStatus {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  // Последний колбэк без переподключения при каждом рендере.
  const onSessionEnded = useRef(options.onSessionEnded);
  useEffect(() => {
    onSessionEnded.current = options.onSessionEnded;
  });

  useEffect(() => {
    const invalidate = (...keys: (readonly unknown[])[]) => {
      for (const queryKey of keys) {
        void queryClient.invalidateQueries({ queryKey });
      }
    };
    const handleEvent = (event: ContestEvent) => {
      switch (event.type) {
        case "ideas_changed":
          invalidate(ideasKey(contestId));
          break;
        case "idea_deleted":
          // Вместе с идеей исчезли голоса: меняются и места, и цифры организатора.
          invalidate(ideasKey(contestId), resultsKey(contestId), dashboardKey(contestId));
          break;
        case "results_changed":
          invalidate(resultsKey(contestId), dashboardKey(contestId));
          break;
      }
    };
    return connectContestEvents(contestId, {
      onEvent: handleEvent,
      onStatus: setStatus,
      onResync: () => {
        invalidate(contestScope(contestId));
      },
      onSessionEnded: () => {
        onSessionEnded.current?.();
      },
    });
  }, [contestId, queryClient]);

  return status;
}
