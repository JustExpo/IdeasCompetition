import { useQuery } from "@tanstack/react-query";

import { getDashboard } from "../../api";
import { dashboardKey } from "../../shared/lib/queryKeys";

/** Период опроса до появления WebSocket (временное отклонение от Р8, убирается в IC-025). */
export const DASHBOARD_POLL_MS = 5000;

export function useDashboard(contestId: number, live: boolean) {
  return useQuery({
    queryKey: dashboardKey(contestId),
    queryFn: () => getDashboard(contestId),
    // После финала цифры не меняются, опрос не нужен; в фоне вкладка не опрашивает сервер,
    // а при возвращении на неё данные перечитываются сразу.
    refetchInterval: live ? DASHBOARD_POLL_MS : false,
    refetchOnWindowFocus: "always",
  });
}
