import { parseEventStream } from "./sse";
import type {
  AssistantTurn,
  ProjectState,
  ProjectSummary,
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

export async function* streamTurn(
  message: string,
  projectId: string | null,
): AsyncGenerator<TurnStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/turns/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, project_id: projectId }),
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
