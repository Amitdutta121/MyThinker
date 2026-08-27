import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addDecision,
  addNextAction,
  ApiError,
  approveProposal,
  createTurn,
  deleteDecision,
  deleteDocument,
  deleteDocuments,
  dismissProposal,
  getMessages,
  getProject,
  listProjects,
  patchDecision,
  patchNextAction,
  patchNorthStar,
  uploadDocument,
} from "@/lib/api-client";
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

describe("getMessages", () => {
  it("returns the replayed transcript on success", async () => {
    const transcript = [
      { role: "user", content: "help me think" },
      { role: "assistant", content: "what's the goal?" },
    ];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(transcript));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getMessages("p1");

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/projects/p1/messages"));
    expect(result).toEqual(transcript);
  });

  it("treats a 404 as an empty transcript", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "missing" }, 404)));

    await expect(getMessages("missing")).resolves.toEqual([]);
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

describe("uploadDocument", () => {
  it("POSTs the raw file with the name in the query and returns the stored doc", async () => {
    const doc = {
      id: "d1",
      project_id: "p1",
      research_task_id: "",
      source_url: "notes.md",
      title: "notes.md",
      content: "# hi",
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(doc, 201));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["# hi"], "notes.md", { type: "text/markdown" });
    const result = await uploadDocument("p1", file);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/documents?filename=notes.md");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(file);
    expect(result.title).toBe("notes.md");
  });

  it("throws an ApiError carrying the backend detail on a 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Unsupported file type" }, 422)),
    );

    const file = new File(["x"], "bad.exe");
    await expect(uploadDocument("p1", file)).rejects.toMatchObject(
      new ApiError(422, "Unsupported file type"),
    );
  });

  it("deleteDocument targets the document id with DELETE and returns the remaining list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    const result = await deleteDocument("p1", "d1");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/documents/d1");
    expect(init.method).toBe("DELETE");
    expect(result).toEqual([]);
  });

  it("deleteDocuments POSTs the id list to the bulk route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDocuments("p1", ["d1", "d2"]);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/documents/delete");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ ids: ["d1", "d2"] });
  });
});

describe("direct-edit mutations", () => {
  it("patchNorthStar PATCHes the title and returns the new state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(projectStateFixture));
    vi.stubGlobal("fetch", fetchMock);

    const result = await patchNorthStar("p1", { title: "Personal KB" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/north-star");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ title: "Personal KB" }));
    expect(result.north_star?.title).toBe("Personal knowledge base");
  });

  it("addDecision POSTs the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(projectStateFixture));
    vi.stubGlobal("fetch", fetchMock);

    await addDecision("p1", { choice: "Single-device for v1", reversible: false });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/decisions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      choice: "Single-device for v1",
      reversible: false,
    });
  });

  it("patchDecision and deleteDecision target the decision id", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(projectStateFixture));
    vi.stubGlobal("fetch", fetchMock);

    await patchDecision("p1", "d9", { rationale: "cheaper" });
    await deleteDecision("p1", "d9");

    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toContain(
      "/projects/p1/decisions/d9",
    );
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[1].method).toBe("DELETE");
  });

  it("approveProposal and dismissProposal hit the proposal routes", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(projectStateFixture));
    vi.stubGlobal("fetch", fetchMock);

    await approveProposal("p1");
    await dismissProposal("p1");

    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toContain(
      "/projects/p1/proposal/approve",
    );
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[1].method).toBe("DELETE");
  });

  it("addNextAction / patchNextAction target the next-actions routes", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse(projectStateFixture));
    vi.stubGlobal("fetch", fetchMock);

    await addNextAction("p1", { description: "Call three users" });
    await patchNextAction("p1", "a3", { completed: true });

    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toContain(
      "/projects/p1/next-actions",
    );
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[0]).toContain(
      "/projects/p1/next-actions/a3",
    );
  });

  it("surfaces a backend 400 as an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Goal cannot be empty." }, 400)),
    );

    await expect(patchNorthStar("p1", { title: "" })).rejects.toMatchObject(
      new ApiError(400, "Goal cannot be empty."),
    );
  });
});
