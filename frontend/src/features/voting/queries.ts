import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, castVote, withdrawVote } from "../../api";
import { contestScope, ideasKey } from "../../shared/lib/queryKeys";

/**
 * Отдать или отозвать голос. После любого исхода список перечитывается: идею могли удалить
 * (404 — она исчезнет из списка), а голосование — закрыться (409 `voting_closed` — сбрасываем
 * все данные конкурса, и экран перейдёт к итогам). Правила фаз остаются на сервере.
 */
export function useVoteMutation(contestId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { ideaId: string; vote: boolean }) =>
      input.vote ? castVote(input.ideaId) : withdrawVote(input.ideaId),
    onSettled: async (_data, error) => {
      const closed = error instanceof ApiError && error.code === "voting_closed";
      await queryClient.invalidateQueries({
        queryKey: closed ? contestScope(contestId) : ideasKey(contestId),
      });
    },
  });
}
