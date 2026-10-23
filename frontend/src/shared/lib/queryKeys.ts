/**
 * Ключи запросов одного конкурса. Все начинаются с общего префикса `contestScope`: страница
 * сбрасывает их разом, когда серверное время пересекает дедлайн, а фичи (идеи, голосование,
 * итоги) обновляют чужие данные по ключу, не импортируя друг друга.
 */
export function contestScope(contestId: number) {
  return ["contest", contestId] as const;
}

export const contestDetailKey = (contestId: number) =>
  [...contestScope(contestId), "detail"] as const;
export const ideasKey = (contestId: number) => [...contestScope(contestId), "ideas"] as const;
export const resultsKey = (contestId: number) => [...contestScope(contestId), "results"] as const;
export const dashboardKey = (contestId: number) =>
  [...contestScope(contestId), "dashboard"] as const;
