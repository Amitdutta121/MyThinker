import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import DecisionHistory from "@/components/workspace-panels/DecisionHistory";
import projectState from "../fixtures/project-state.sample.json";
import type { Decision } from "@/lib/types";

describe("DecisionHistory", () => {
  it("shows a placeholder when there are no decisions", () => {
    render(<DecisionHistory decisions={[]} />);

    expect(screen.getByText("No decisions made yet.")).toBeInTheDocument();
  });

  it("renders the choice and reversibility badge", () => {
    render(<DecisionHistory decisions={projectState.decisions as Decision[]} />);

    expect(screen.getByText("Single-device for v1")).toBeInTheDocument();
    expect(screen.getByText("reversible")).toBeInTheDocument();
  });
});
