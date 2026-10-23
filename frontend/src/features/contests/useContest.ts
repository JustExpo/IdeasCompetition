import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { getContest } from "../../api";
import { contestDetailKey } from "../../shared/lib/queryKeys";
import { serverClock } from "../../shared/lib/serverTime";

/** Карточка конкурса; серверное время из ответа сверяет часы клиента для таймеров и дедлайнов. */
export function useContest(contestId: number) {
  const query = useQuery({
    queryKey: contestDetailKey(contestId),
    queryFn: () => getContest(contestId),
  });
  const serverTime = query.data?.server_time;
  useEffect(() => {
    if (serverTime !== undefined) {
      serverClock.sync(serverTime);
    }
  }, [serverTime]);
  return query;
}
