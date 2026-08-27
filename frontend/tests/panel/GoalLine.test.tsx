import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GoalLine from "@/components/panel/GoalLine";
import { patchNorthStar } from "@/lib/api-client";
import projectState from "../fixtures/project-state.sample.json";
import type { ProjectState } from "@/lib/types";

vi.mock("@/lib/api-client", () => ({
  patchNorthStar: vi.fn(),
}));

const nextState = { ...projectState, north_star: { title: "Renamed" } } as unknown as ProjectState;

beforeEach(() => {
  vi.mocked(patchNorthStar).mockReset().mockResolvedValue(nextState);
});

describe("GoalLine", () => {
  it("shows the current goal", () => {
    render(<GoalLine projectId="p1" title="Personal KB" onStateChange={vi.fn()} />);
    expect(screen.getByText("Personal KB")).toBeInTheDocument();
  });

  it("saves an edited goal and lifts the returned state", async () => {
    const onStateChange = vi.fn();
    render(<GoalLine projectId="p1" title="Personal KB" onStateChange={onStateChange} />);

    await userEvent.click(screen.getByRole("button", { name: /edit the goal/i }));
    const input = screen.getByRole("textbox", { name: /edit the goal/i });
    await userEvent.clear(input);
    await userEvent.type(input, "Renamed{Enter}");

    expect(patchNorthStar).toHaveBeenCalledWith("p1", { title: "Renamed" });
    expect(onStateChange).toHaveBeenCalledWith(nextState);
  });

  it("does not call the API when the goal is unchanged", async () => {
    render(<GoalLine projectId="p1" title="Personal KB" onStateChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /edit the goal/i }));
    await userEvent.keyboard("{Enter}");
    expect(patchNorthStar).not.toHaveBeenCalled();
  });
});
