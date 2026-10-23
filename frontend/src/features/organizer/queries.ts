import { useQuery } from "@tanstack/react-query";

import { getDashboard } from "../../api";
import { dashboardKey } from "../../shared/lib/queryKeys";

/**
 * Цифры организатора обновляются сигналами `results_changed` (WebSocket, Р8), поэтому опроса
 * нет. При возвращении на вкладку данные всё равно перечитываются: сигнал мог пропасть вместе
 * со связью.
 */
export function useDashboard(contestId: number) {
  return useQuery({
    queryKey: dashboardKey(contestId),
    queryFn: () => getDashboard(contestId),
    refetchOnWindowFocus: "always",
  });
}
