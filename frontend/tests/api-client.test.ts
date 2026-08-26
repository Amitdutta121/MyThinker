import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createTurn, getProject, listProjects } from "@/lib/api-client";
import projectStateFixture from "./fixtures/project-state.sample.json";
import projectSummariesFixture from "./fixtures/project-summaries.sample.json";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listProjects", () => {
  it("fetches and parses project summaries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(projectSummariesFixture));
    vi.stubGlobal("fetch", fetchMock);

    const result = await listProjects(5);

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/projects?limit=5"));
    expect(result).toHaveLength(2);
    expect(result[0].title).toBe("Personal knowledge base");
  });
});

describe("getProject", () => {
  it("returns null on a 404 instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "missing" }, 404)));

    const result = await getProject("missing");

    expect(result).toBeNull();
  });

  it("returns the full project state on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(projectStateFixture)));

    const result = await getProject("proj-fixture-1");

    expect(result?.branches).toHaveLength(2);
    expect(result?.north_star?.title).toBe("Personal knowledge base");
  });
});

describe("createTurn", () => {
  it("throws an ApiError carrying the status and detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "bad request" }, 400)));

    await expect(createTurn("hi", null)).rejects.toMatchObject(
      new ApiError(400, "bad request"),
    );
  });

  it("posts the message and project id", async () => {
    const turn = { project_id: "p1", mode: "capture", message: "ok", question: "" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(turn));
    vi.stubGlobal("fetch", fetchMock);

    const result = await createTurn("hello", "p1");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/turns"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "hello", project_id: "p1" }),
      }),
    );
    expect(result.message).toBe("ok");
  });
});
