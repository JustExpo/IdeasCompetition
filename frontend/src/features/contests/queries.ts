import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createContest, listContests } from "../../api";

export const contestKeys = {
  all: ["contests"] as const,
  list: (offset: number) => ["contests", "list", offset] as const,
};

export function useContests(offset: number) {
  return useQuery({
    queryKey: contestKeys.list(offset),
    queryFn: () => listContests(offset),
    // Листание страниц не должно мигать пустым экраном.
    placeholderData: keepPreviousData,
  });
}

export function useCreateContest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createContest,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: contestKeys.all });
    },
  });
}
