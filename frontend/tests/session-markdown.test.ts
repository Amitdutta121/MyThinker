import { describe, expect, it } from "vitest";
import { sessionToMarkdown } from "@/lib/session-markdown";
import projectState from "./fixtures/project-state.sample.json";
import type { ProjectState } from "@/lib/types";

const state = projectState as unknown as ProjectState;

describe("sessionToMarkdown", () => {
  it("renders the north star title as the H1", () => {
    expect(sessionToMarkdown(state)).toMatch(/^# Personal knowledge base\n/);
  });

  it("includes decisions, the plan, and open research questions", () => {
    const md = sessionToMarkdown(state);
    expect(md).toContain("## Decisions");
    expect(md).toContain("**Single-device for v1**");
    expect(md).toContain("## Plan — next steps");
    expect(md).toContain("1. Prototype SQLite FTS5 search over 100 sample notes. _(60m)_");
    expect(md).toContain("## Open research questions");
  });

  it("omits sections with no content", () => {
    const bare = { schema_version: 2, current_mode: "capture" } as unknown as ProjectState;
    const md = sessionToMarkdown(bare);
    expect(md).toBe("# Untitled session\n");
  });

  it("skips completed and stale next actions", () => {
    const withStale = {
      ...state,
      next_actions: [
        ...(state.next_actions ?? []),
        {
          id: "n2",
          description: "stale step",
          success_signal: "",
          failure_signal: "",
          time_box_minutes: 30,
          implementation_intention: "",
          completed: false,
          stale: true,
        },
      ],
    } as unknown as ProjectState;
    expect(sessionToMarkdown(withStale)).not.toContain("stale step");
  });
});
