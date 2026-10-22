import { apiClient, unwrap } from "./client";
import type { components } from "./schema.gen";

export type ContestCreateRequest = components["schemas"]["CreateContestRequest"];
export type ContestList = components["schemas"]["ContestListResponse"];
export type ContestPhase = components["schemas"]["ContestPhase"];
export type ContestSummary = components["schemas"]["ContestResponse"];

export const CONTESTS_PAGE_SIZE = 20;

export async function listContests(
  offset: number,
  limit = CONTESTS_PAGE_SIZE,
): Promise<ContestList> {
  return unwrap(await apiClient.GET("/api/contests", { params: { query: { limit, offset } } }));
}

export async function createContest(input: ContestCreateRequest): Promise<ContestSummary> {
  return unwrap(await apiClient.POST("/api/contests", { body: input }));
}
