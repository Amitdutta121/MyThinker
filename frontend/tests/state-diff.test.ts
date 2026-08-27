import { describe, expect, it } from "vitest";
import { summarizeStateChange } from "@/lib/state-diff";
import sample from "./fixtures/project-state.sample.json";
import type { ProjectState } from "@/lib/types";

const base = sample as unknown as ProjectState;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const clone = (): any => JSON.parse(JSON.stringify(base));

describe("summarizeStateChange", () => {
  it("returns nothing when there is no previous state", () => {
    expect(summarizeStateChange(null, clone())).toEqual([]);
  });

  it("returns nothing when nothing changed", () => {
    expect(summarizeStateChange(clone(), clone())).toEqual([]);
  });

  it("reports added assumptions with a count", () => {
    const next = clone();
    next.assumptions = [
      ...next.assumptions,
      { id: "a3", statement: "x", status: "untested", importance: 2, falsifying_evidence: "" },
    ];
    expect(summarizeStateChange(clone(), next)).toContain("1 assumption added");
  });

  it("reports a recorded decision and a committed proposal together", () => {
    const prev = clone();
    const next = clone();
    next.proposal = null;
    next.decisions = [
      ...next.decisions,
      {
        id: "d2",
        question: "q",
        choice: "c",
        rationale: "",
        alternatives: [],
        reversible: true,
        decided_at: "2026-08-26T10:00:00Z",
      },
    ];
    const summary = summarizeStateChange(prev, next);
    expect(summary).toContain("1 decision recorded");
    expect(summary).toContain("Proposal committed");
  });

  it("notices a north star edit", () => {
    const next = clone();
    next.north_star = { ...next.north_star, current_hypothesis: "something new" };
    expect(summarizeStateChange(clone(), next)).toContain("North star updated");
  });
});
