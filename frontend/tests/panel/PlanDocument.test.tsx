import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlanDocument from "@/components/panel/PlanDocument";
import { addNextAction } from "@/lib/api-client";
import projectState from "../fixtures/project-state.sample.json";
import type { NextAction, ProjectState } from "@/lib/types";

vi.mock("@/lib/api-client", () => ({
  addNextAction: vi.fn(),
  patchNextAction: vi.fn(),
  deleteNextAction: vi.fn(),
}));

const state = projectState as unknown as ProjectState;

beforeEach(() => {
  vi.mocked(addNextAction).mockReset().mockResolvedValue(state);
});

describe("PlanDocument", () => {
  it("renders the committed direction and a step as prose", () => {
    render(<PlanDocument projectId="p1" state={state} onStateChange={vi.fn()} />);

    expect(screen.getByText(/Working toward/)).toBeInTheDocument();
    expect(
      screen.getByText(/Prototype SQLite FTS5 search over 100 sample notes/),
    ).toBeInTheDocument();
    expect(screen.getByText(/60m/)).toBeInTheDocument();
    expect(screen.getByText(/done when: Search returns relevant results/)).toBeInTheDocument();
  });

  it("marks a user-added step and flags a stale one", () => {
    const mine: NextAction = {
      id: "u1",
      description: "Interview three note-app users",
      success_signal: "",
      failure_signal: "",
      time_box_minutes: 30,
      implementation_intention: "",
      completed: false,
      stale: true,
      origin: "user",
    };
    render(
      <PlanDocument
        projectId="p1"
        state={{ ...state, next_actions: [mine] } as ProjectState}
        onStateChange={vi.fn()}
      />,
    );

    expect(screen.getByText(/added by you/)).toBeInTheDocument();
    expect(screen.getByText(/May be out of date/)).toBeInTheDocument();
  });

  it("adds a manual step through the API and lifts the new state", async () => {
    const onStateChange = vi.fn();
    render(<PlanDocument projectId="p1" state={state} onStateChange={onStateChange} />);

    await userEvent.click(screen.getByRole("button", { name: "+ Add a step" }));
    const box = screen.getByRole("textbox", { name: /new plan step/i });
    await userEvent.type(box, "Sketch the capture flow");
    await userEvent.click(screen.getByRole("button", { name: "Add step" }));

    expect(addNextAction).toHaveBeenCalledWith("p1", {
      description: "Sketch the capture flow",
    });
    expect(onStateChange).toHaveBeenCalledWith(state);
  });
});
