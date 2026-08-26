import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import BranchGraph from "@/components/workspace-panels/BranchGraph";
import projectState from "../fixtures/project-state.sample.json";
import type { IdeaBranch } from "@/lib/types";

describe("BranchGraph", () => {
  it("shows a placeholder when there are no branches", () => {
    render(<BranchGraph branches={[]} />);

    expect(screen.getByText("No branches yet.")).toBeInTheDocument();
  });

  it("groups branches into lanes by status", () => {
    render(<BranchGraph branches={projectState.branches as IdeaBranch[]} />);

    expect(screen.getByTestId("branch-lane-active")).toHaveTextContent("Local-first app");
    expect(screen.getByTestId("branch-lane-parked")).toHaveTextContent("Browser extension clipper");
  });
});
