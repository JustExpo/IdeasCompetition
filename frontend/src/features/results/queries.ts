import { useQuery } from "@tanstack/react-query";

import { getResults } from "../../api";
import { resultsKey } from "../../shared/lib/queryKeys";

export function useResults(contestId: number, enabled: boolean) {
  return useQuery({
    queryKey: resultsKey(contestId),
    queryFn: () => getResults(contestId),
    enabled,
  });
}
