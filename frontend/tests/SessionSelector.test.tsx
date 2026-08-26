import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SessionSelector from "@/components/SessionSelector";
import projectSummaries from "./fixtures/project-summaries.sample.json";
import type { ProjectSummary } from "@/lib/types";

describe("SessionSelector", () => {
  it("opens to list recent sessions and fires onSelect", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <SessionSelector
        projects={projectSummaries as ProjectSummary[]}
        currentProjectId={null}
        onSelect={onSelect}
        onNewSession={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Sessions \(2\)/ }));
    await user.click(screen.getByText("Weekend trip planning"));

    expect(onSelect).toHaveBeenCalledWith("proj-fixture-2");
  });

  it("fires onNewSession from the list", async () => {
    const user = userEvent.setup();
    const onNewSession = vi.fn();

    render(
      <SessionSelector
        projects={projectSummaries as ProjectSummary[]}
        currentProjectId={null}
        onSelect={vi.fn()}
        onNewSession={onNewSession}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Sessions/ }));
    await user.click(screen.getByText("+ New session"));

    expect(onNewSession).toHaveBeenCalledOnce();
  });
});
