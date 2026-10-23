import { apiClient, unwrap } from "./client";
import type { components } from "./schema.gen";

type Schemas = components["schemas"];

export type ContestDetail = Schemas["ContestDetailResponse"];
export type ContestAction = Schemas["ContestAction"];
export type OwnIdea = Schemas["OwnIdeaItem"];
export type VotingIdea = Schemas["VotingIdeaItem"];
export type FinishedIdea = Schemas["FinishedIdeaItem"];
export type IdeasListing =
  | Schemas["SubmissionIdeasResponse"]
  | Schemas["VotingIdeasResponse"]
  | Schemas["FinishedIdeasResponse"];
export type SavedIdea = Schemas["IdeaResponse"];
export type ResultItem = Schemas["ResultItem"];
export type FinalResultItem = Schemas["FinalResultItem"];
export type ContestResults = Schemas["InProgressResultsResponse"] | Schemas["FinalResultsResponse"];
export type Dashboard = Schemas["DashboardResponse"];

export async function getContest(contestId: number): Promise<ContestDetail> {
  return unwrap(
    await apiClient.GET("/api/contests/{contest_id}", {
      params: { path: { contest_id: contestId } },
    }),
  );
}

export async function listIdeas(contestId: number): Promise<IdeasListing> {
  return unwrap(
    await apiClient.GET("/api/contests/{contest_id}/ideas", {
      params: { path: { contest_id: contestId } },
    }),
  );
}

export interface IdeaDraft {
  title: string;
  description: string;
}

/** `clientRequestId` создаётся при открытии формы: повтор после обрыва не создаёт вторую идею. */
export async function submitIdea(
  contestId: number,
  draft: IdeaDraft,
  clientRequestId: string,
): Promise<SavedIdea> {
  return unwrap(
    await apiClient.POST("/api/contests/{contest_id}/ideas", {
      params: { path: { contest_id: contestId } },
      body: { ...draft, client_request_id: clientRequestId },
    }),
  );
}

export async function editIdea(
  ideaId: string,
  draft: IdeaDraft,
  version: number,
): Promise<SavedIdea> {
  return unwrap(
    await apiClient.PATCH("/api/ideas/{idea_id}", {
      params: { path: { idea_id: ideaId } },
      body: { ...draft, version },
    }),
  );
}

export async function deleteIdea(ideaId: string): Promise<void> {
  unwrap(await apiClient.DELETE("/api/ideas/{idea_id}", { params: { path: { idea_id: ideaId } } }));
}

export async function castVote(ideaId: string): Promise<void> {
  unwrap(
    await apiClient.PUT("/api/ideas/{idea_id}/vote", { params: { path: { idea_id: ideaId } } }),
  );
}

export async function withdrawVote(ideaId: string): Promise<void> {
  unwrap(
    await apiClient.DELETE("/api/ideas/{idea_id}/vote", {
      params: { path: { idea_id: ideaId } },
    }),
  );
}

export async function getResults(contestId: number): Promise<ContestResults> {
  return unwrap(
    await apiClient.GET("/api/contests/{contest_id}/results", {
      params: { path: { contest_id: contestId } },
    }),
  );
}

export async function getDashboard(contestId: number): Promise<Dashboard> {
  return unwrap(
    await apiClient.GET("/api/organizer/contests/{contest_id}/dashboard", {
      params: { path: { contest_id: contestId } },
    }),
  );
}
