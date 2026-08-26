import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import EvidenceTimeline from "@/components/workspace-panels/EvidenceTimeline";
import projectState from "../fixtures/project-state.sample.json";
import type { EvidenceItem } from "@/lib/types";

describe("EvidenceTimeline", () => {
  it("sorts evidence newest first", () => {
    render(<EvidenceTimeline evidence={projectState.evidence as EvidenceItem[]} />);

    const claims = screen.getAllByText(/handles 50k notes|never revisited/);
    expect(claims[0]).toHaveTextContent("SQLite FTS5 handles 50k notes");
  });

  it("renders a source link when present", () => {
    render(<EvidenceTimeline evidence={projectState.evidence as EvidenceItem[]} />);

    expect(screen.getByRole("link", { name: "SQLite FTS5 docs" })).toHaveAttribute(
      "href",
      "https://www.sqlite.org/fts5.html",
    );
  });
});
