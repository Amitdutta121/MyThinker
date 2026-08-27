import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DecisionsList from "@/components/panel/DecisionsList";
import { approveProposal, dismissProposal } from "@/lib/api-client";
import projectState from "../fixtures/project-state.sample.json";
import type { ProjectState } from "@/lib/types";

vi.mock("@/lib/api-client", () => ({
  approveProposal: vi.fn(),
  dismissProposal: vi.fn(),
  addDecision: vi.fn(),
  patchDecision: vi.fn(),
  deleteDecision: vi.fn(),
}));

const state = projectState as unknown as ProjectState;

beforeEach(() => {
  vi.mocked(approveProposal).mockReset().mockResolvedValue(state);
  vi.mocked(dismissProposal).mockReset().mockResolvedValue(state);
});

describe("DecisionsList", () => {
  it("shows the pending proposal with an Approve action", async () => {
    const onStateChange = vi.fn();
    render(
      <DecisionsList projectId="p1" state={state} onStateChange={onStateChange} />,
    );

    expect(screen.getByText(/Pending — your call/)).toBeInTheDocument();
    expect(
      screen.getByText(/Build the local-first desktop app first/),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(approveProposal).toHaveBeenCalledWith("p1");
    expect(onStateChange).toHaveBeenCalledWith(state);
  });

  it("opens a decision in a modal when its row is clicked", async () => {
    render(<DecisionsList projectId="p1" state={state} onStateChange={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Single-device for v1/ }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/Sync between devices or single-device only/);
    expect(dialog).toHaveTextContent(/reversible/);
  });

  it("reveals an input for a manually added decision", async () => {
    render(<DecisionsList projectId="p1" state={state} onStateChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "+ Add a decision" }));
    expect(screen.getByRole("textbox", { name: /new decision/i })).toBeInTheDocument();
  });
});
