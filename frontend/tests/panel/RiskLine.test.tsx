import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskLine from "@/components/panel/RiskLine";
import type { ProjectState } from "@/lib/types";

const base = (): ProjectState =>
  ({
    project_id: "p1",
    north_star: { title: "x" },
    next_actions: [],
    assumptions: [],
    decisions: [],
    branches: [],
    evidence: [],
    research_tasks: [],
    open_questions: [],
    parked_ideas: [],
  }) as unknown as ProjectState;

describe("RiskLine", () => {
  it("renders nothing when there is no risk", () => {
    const { container } = render(<RiskLine state={base()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("warns about a stale plan step first", () => {
    const state = base();
    state.next_actions = [
      { id: "a1", description: "old step", stale: true, completed: false } as never,
    ];
    render(<RiskLine state={state} />);
    expect(screen.getByText(/plan may be out of date/i)).toBeInTheDocument();
  });

  it("warns about a shaky high-importance assumption", () => {
    const state = base();
    state.assumptions = [
      {
        id: "s1",
        statement: "users trust local-only",
        status: "challenged",
        importance: 5,
      } as never,
    ];
    render(<RiskLine state={state} />);
    expect(screen.getByText(/shaky assumption/i)).toBeInTheDocument();
  });

  it("prompts to approve a pending proposal", () => {
    const state = base();
    state.proposal = { statement: "do X" } as never;
    render(<RiskLine state={state} />);
    expect(screen.getByText(/waiting for your approval/i)).toBeInTheDocument();
  });

  it("hands the instruction to the composer on Fix", async () => {
    const state = base();
    state.assumptions = [
      { id: "s1", statement: "risky belief", status: "challenged", importance: 4 } as never,
    ];
    const onPrefill = vi.fn();
    render(<RiskLine state={state} onPrefillComposer={onPrefill} />);
    await userEvent.click(screen.getByRole("button", { name: "Fix" }));
    expect(onPrefill).toHaveBeenCalledWith(expect.stringContaining("risky belief"));
  });
});
