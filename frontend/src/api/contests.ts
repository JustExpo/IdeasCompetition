import { apiClient, unwrap } from "./client";
import type {
  ContestCreateRequest,
  ContestList,
  ContestPhase,
  ContestSummary,
} from "./pendingContracts";

export type { ContestCreateRequest, ContestList, ContestPhase, ContestSummary };

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
