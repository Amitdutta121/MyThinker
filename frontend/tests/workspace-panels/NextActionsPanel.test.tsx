import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import NextActionsPanel from "@/components/workspace-panels/NextActionsPanel";
import projectState from "../fixtures/project-state.sample.json";
import type { NextAction } from "@/lib/types";

describe("NextActionsPanel", () => {
  it("renders the description and time box", () => {
    render(<NextActionsPanel nextActions={projectState.next_actions as NextAction[]} />);

    expect(screen.getByText(/Prototype SQLite FTS5 search/)).toBeInTheDocument();
    expect(screen.getByText("60m")).toBeInTheDocument();
  });

  it("strikes through completed actions", () => {
    const completed: NextAction = {
      ...(projectState.next_actions[0] as NextAction),
      completed: true,
    };
    render(<NextActionsPanel nextActions={[completed]} />);

    expect(screen.getByText(/Prototype SQLite FTS5 search/)).toHaveClass("line-through");
  });
});
