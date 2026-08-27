import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WorkingNotesDrawer from "@/components/panel/WorkingNotesDrawer";
import projectState from "../fixtures/project-state.sample.json";
import type { ProjectState } from "@/lib/types";

const state = projectState as unknown as ProjectState;

describe("WorkingNotesDrawer", () => {
  it("is collapsed by default and shows the total count", () => {
    render(<WorkingNotesDrawer state={state} />);
    const toggle = screen.getByRole("button", { name: /working notes/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    // 2 assumptions + 2 evidence + 2 branches + 2 research + 2 loose ends
    expect(toggle).toHaveTextContent("10");
  });

  it("renders nothing when the agent has no notes", () => {
    const empty = {
      ...state,
      assumptions: [],
      evidence: [],
      branches: [],
      research_tasks: [],
      open_questions: [],
      parked_ideas: [],
    } as ProjectState;
    const { container } = render(<WorkingNotesDrawer state={empty} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("expands and opens a read-only modal for an assumption", async () => {
    render(<WorkingNotesDrawer state={state} />);
    await userEvent.click(screen.getByRole("button", { name: /working notes/i }));

    const row = screen.getByRole("button", {
      name: /trust a local-only store/i,
    });
    await userEvent.click(row);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/Falsified if/i);
    expect(dialog).toHaveTextContent(/agent maintains this/i);
  });
});
