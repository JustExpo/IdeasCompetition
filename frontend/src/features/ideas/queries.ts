import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  deleteIdea,
  describeError,
  editIdea,
  listIdeas,
  submitIdea,
  type IdeaDraft,
} from "../../api";
import { reportLateAction } from "../../shared/lib/lateAction";
import { contestScope, ideasKey } from "../../shared/lib/queryKeys";

/** Список идей конкурса в том виде, в каком его вправе видеть текущий пользователь (по фазе). */
export function useIdeasListing(contestId: number) {
  return useQuery({
    queryKey: ideasKey(contestId),
    queryFn: () => listIdeas(contestId),
  });
}

/**
 * Запись отклонена из-за закрытия приёма: страница открыта дольше дедлайна. Сбрасываем все данные
 * конкурса, чтобы экран перешёл в фазу голосования; текст в форме остаётся у пользователя.
 */
function isSubmissionClosed(error: unknown): boolean {
  return error instanceof ApiError && error.code === "submission_closed";
}

export function useSubmitIdea(contestId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { draft: IdeaDraft; clientRequestId: string }) =>
      submitIdea(contestId, input.draft, input.clientRequestId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ideasKey(contestId) });
    },
    onError: async (error) => {
      if (isSubmissionClosed(error)) {
        reportLateAction(describeError(error).message);
        await queryClient.invalidateQueries({ queryKey: contestScope(contestId) });
      }
    },
  });
}

export function useEditIdea(contestId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { ideaId: string; draft: IdeaDraft; version: number }) =>
      editIdea(input.ideaId, input.draft, input.version),
    // Список перечитывается и при ошибке: после `stale_version` в нём уже новая версия идеи,
    // и повторное сохранение осознанно перезапишет её текстом из формы.
    onSettled: async (_data, error) => {
      if (isSubmissionClosed(error)) {
        reportLateAction(describeError(error).message);
      }
      await queryClient.invalidateQueries({
        queryKey: isSubmissionClosed(error) ? contestScope(contestId) : ideasKey(contestId),
      });
    },
  });
}

export function useDeleteIdea(contestId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteIdea,
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ideasKey(contestId) });
    },
  });
}
