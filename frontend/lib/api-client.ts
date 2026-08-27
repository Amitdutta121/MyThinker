import { parseEventStream } from "./sse";
import type {
  AssistantTurn,
  ProjectState,
  ProjectSummary,
  ResearchDocument,
  TranscriptMessage,
  TurnStreamEvent,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // fall through to the generic message below
  }
  return `${response.status} ${response.statusText}`;
}

export async function listProjects(limit = 20): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_BASE_URL}/projects?limit=${limit}`);
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ProjectSummary[];
}

export async function getProject(projectId: string): Promise<ProjectState | null> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ProjectState;
}

export async function getMessages(projectId: string): Promise<TranscriptMessage[]> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/messages`);
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as TranscriptMessage[];
}

export async function getDocuments(projectId: string): Promise<ResearchDocument[]> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/documents`);
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ResearchDocument[];
}

/**
 * Upload a file (PDF / text / Markdown) into a project's document store so it
 * can be cited in later turns. The backend takes the raw bytes as the request
 * body with the name in a query param (no multipart parser dependency).
 */
export async function uploadDocument(
  projectId: string,
  file: File,
): Promise<ResearchDocument> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/documents?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ResearchDocument;
}

/**
 * Remove one stored source from a project. Returns the remaining documents so
 * the caller can lift them straight into state without a second round-trip.
 */
export async function deleteDocument(
  projectId: string,
  documentId: string,
): Promise<ResearchDocument[]> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/documents/${documentId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ResearchDocument[];
}

/**
 * Remove several stored sources in one request. Unknown ids are ignored by the
 * backend. Returns the remaining documents.
 */
export async function deleteDocuments(
  projectId: string,
  ids: string[],
): Promise<ResearchDocument[]> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/documents/delete`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ResearchDocument[];
}

export async function createTurn(
  message: string,
  projectId: string | null,
): Promise<AssistantTurn> {
  const response = await fetch(`${API_BASE_URL}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, project_id: projectId }),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as AssistantTurn;
}

/**
 * Direct-edit mutations. Each hits a `/projects/{id}/...` route that changes the
 * board without an agent turn and returns the full updated `ProjectState`, which
 * the caller lifts into `Workspace` state. `KeyError` -> 404, `ValueError` -> 400
 * on the backend, both surfaced here as `ApiError`.
 */
async function mutateState(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown,
): Promise<ProjectState> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  return (await response.json()) as ProjectState;
}

export function patchNorthStar(
  projectId: string,
  patch: { title?: string },
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/north-star`, "PATCH", patch);
}

export function addDecision(
  projectId: string,
  body: { question?: string; choice: string; rationale?: string; reversible?: boolean },
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/decisions`, "POST", body);
}

export function patchDecision(
  projectId: string,
  decisionId: string,
  patch: { question?: string; choice?: string; rationale?: string; reversible?: boolean },
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/decisions/${decisionId}`, "PATCH", patch);
}

export function deleteDecision(
  projectId: string,
  decisionId: string,
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/decisions/${decisionId}`, "DELETE");
}

export function approveProposal(projectId: string): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/proposal/approve`, "POST");
}

export function dismissProposal(projectId: string): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/proposal`, "DELETE");
}

export function addNextAction(
  projectId: string,
  body: {
    description: string;
    time_box_minutes?: number;
    implementation_intention?: string;
    success_signal?: string;
    failure_signal?: string;
  },
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/next-actions`, "POST", body);
}

export function patchNextAction(
  projectId: string,
  actionId: string,
  patch: {
    description?: string;
    time_box_minutes?: number;
    implementation_intention?: string;
    success_signal?: string;
    failure_signal?: string;
    completed?: boolean;
  },
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/next-actions/${actionId}`, "PATCH", patch);
}

export function deleteNextAction(
  projectId: string,
  actionId: string,
): Promise<ProjectState> {
  return mutateState(`/projects/${projectId}/next-actions/${actionId}`, "DELETE");
}

export async function* streamTurn(
  message: string,
  projectId: string | null,
  signal?: AbortSignal,
): AsyncGenerator<TurnStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/turns/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, project_id: projectId }),
    signal,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  if (!response.body) {
    throw new Error("Streaming response had no body");
  }

  for await (const payload of parseEventStream(response.body)) {
    yield JSON.parse(payload) as TurnStreamEvent;
  }
}
