import type { components } from "./api-types";

export type ThinkingMode = components["schemas"]["ThinkingMode"];
export type ProjectState = components["schemas"]["ProjectState"];
export type ProjectSummary = components["schemas"]["ProjectSummary"];
export type AssistantTurn = components["schemas"]["AssistantTurn"];
export type NorthStar = components["schemas"]["NorthStar"];
export type DirectionProposal = components["schemas"]["DirectionProposal"];
export type IdeaBranch = components["schemas"]["IdeaBranch"];
export type BranchStatus = components["schemas"]["BranchStatus"];
export type Assumption = components["schemas"]["Assumption"];
export type EvidenceItem = components["schemas"]["EvidenceItem"];
export type EvidenceKind = components["schemas"]["EvidenceKind"];
export type ResearchTask = components["schemas"]["ResearchTask"];
export type ResearchTaskStatus = components["schemas"]["ResearchTaskStatus"];
export type Decision = components["schemas"]["Decision"];
export type NextAction = components["schemas"]["NextAction"];
export type ResearchDocument = components["schemas"]["Document"];
export type TranscriptMessage = components["schemas"]["ChatMessage"];

/**
 * `POST /turns/stream` returns `StreamingResponse`, so FastAPI's OpenAPI
 * schema can't describe its body (see `create_turn_stream_turns_stream_post`
 * in `api-types.ts`, whose 200 content is `unknown`). This mirrors
 * `TurnStreamEvent`/`TurnStreamEventType` in `src/mythinking/state.py` by
 * hand; keep it in sync with that module, the schema authority.
 */
export type TurnStreamEventType = "node" | "token" | "turn" | "error";

export interface TurnStreamEvent {
  type: TurnStreamEventType;
  node: string;
  mode: ThinkingMode | null;
  turn: AssistantTurn | null;
  detail: string;
}
