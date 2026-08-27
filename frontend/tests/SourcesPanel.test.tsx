import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SourcesPanel from "@/components/SourcesPanel";
import type { ResearchDocument } from "@/lib/types";

function doc(overrides: Partial<ResearchDocument> = {}): ResearchDocument {
  return {
    id: "d1",
    project_id: "p1",
    research_task_id: "",
    source_url: "notes.md",
    title: "notes.md",
    content: "# Heading\n\nExtracted body text.",
    ...overrides,
  } as ResearchDocument;
}

describe("SourcesPanel", () => {
  it("shows an empty prompt and a disabled Add button before a session exists", () => {
    render(<SourcesPanel documents={[]} onUploadFile={vi.fn()} canAttach={false} />);

    expect(screen.getByText(/No sources yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add source/ })).toBeDisabled();
  });

  it("uploads a chosen file and shows a pending row", () => {
    const onUploadFile = vi.fn().mockReturnValue(new Promise(() => {}));
    const { container } = render(
      <SourcesPanel documents={[]} onUploadFile={onUploadFile} canAttach />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["# hi"], "paper.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(onUploadFile).toHaveBeenCalledWith(file);
    expect(screen.getByText("paper.pdf")).toBeInTheDocument();
  });

  it("rejects an unsupported file without calling the uploader", () => {
    const onUploadFile = vi.fn();
    const { container } = render(
      <SourcesPanel documents={[]} onUploadFile={onUploadFile} canAttach />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.zip")] } });

    expect(onUploadFile).not.toHaveBeenCalled();
    expect(screen.getByText(/PDF, text, or Markdown only/)).toBeInTheDocument();
  });

  it("lists stored sources and opens a reader on click", async () => {
    render(<SourcesPanel documents={[doc()]} onUploadFile={vi.fn()} canAttach />);

    await userEvent.click(screen.getByRole("button", { name: /notes\.md/ }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Extracted body text.");
  });

  it("deletes a source through the inline confirm", async () => {
    const onDeleteDocument = vi.fn();
    render(
      <SourcesPanel
        documents={[doc()]}
        onUploadFile={vi.fn()}
        onDeleteDocument={onDeleteDocument}
        canAttach
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete notes.md" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onDeleteDocument).toHaveBeenCalledWith("d1");
  });

  it("renders no delete control when onDeleteDocument is omitted", () => {
    render(<SourcesPanel documents={[doc()]} onUploadFile={vi.fn()} canAttach />);

    expect(screen.queryByRole("button", { name: /^Delete / })).not.toBeInTheDocument();
  });

  it("multi-selects rows and bulk-deletes them after confirm", async () => {
    const onDeleteDocuments = vi.fn();
    render(
      <SourcesPanel
        documents={[
          doc({ id: "d1", title: "one.md", source_url: "one.md" }),
          doc({ id: "d2", title: "two.md", source_url: "two.md" }),
        ]}
        onUploadFile={vi.fn()}
        onDeleteDocuments={onDeleteDocuments}
        canAttach
      />,
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "Select one.md" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Select two.md" }));

    expect(screen.getByText("2 selected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onDeleteDocuments).toHaveBeenCalledWith(["d1", "d2"]);
  });

  it("selects and clears every row from the selection bar", async () => {
    render(
      <SourcesPanel
        documents={[
          doc({ id: "d1", title: "one.md", source_url: "one.md" }),
          doc({ id: "d2", title: "two.md", source_url: "two.md" }),
        ]}
        onUploadFile={vi.fn()}
        onDeleteDocuments={vi.fn()}
        canAttach
      />,
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "Select one.md" }));
    await userEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByText("2 selected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
  });

  it("has no selection UI when onDeleteDocuments is omitted", () => {
    render(<SourcesPanel documents={[doc()]} onUploadFile={vi.fn()} canAttach />);

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("collapses to a rail when asked", () => {
    render(
      <SourcesPanel
        documents={[doc()]}
        onUploadFile={vi.fn()}
        canAttach
        collapsed
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.getByText(/Sources \(1\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add source/ })).not.toBeInTheDocument();
  });
});
