import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPanel from "@/components/ChatPanel";

describe("ChatPanel", () => {
  it("submits the draft and clears the composer on Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<ChatPanel messages={[]} liveSteps={[]} isStreaming={false} error={null} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText("What's on your mind?");
    await user.type(textarea, "Help me think this through{Enter}");

    expect(onSubmit).toHaveBeenCalledWith("Help me think this through");
    expect(textarea).toHaveValue("");
  });

  it("does not submit on Shift+Enter, allowing a newline", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<ChatPanel messages={[]} liveSteps={[]} isStreaming={false} error={null} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText("What's on your mind?");
    await user.type(textarea, "line one{Shift>}{Enter}{/Shift}line two");

    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("line one\nline two");
  });

  it("renders live thinking steps with human labels while streaming", () => {
    render(
      <ChatPanel
        messages={[]}
        liveSteps={[
          { node: "web_search", mode: null },
          { node: "converge_ideas", mode: "converge" },
        ]}
        isStreaming
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    const steps = screen.getAllByTestId("live-step");
    expect(steps).toHaveLength(2);
    expect(steps[0]).toHaveTextContent("Searching the web");
    expect(steps[1]).toHaveTextContent("Weighing tradeoffs");
    // The raw tool identifier is never shown.
    expect(steps[0]).not.toHaveTextContent("web_search");
  });

  it("shows onboarding examples when the transcript is empty", () => {
    render(<ChatPanel messages={[]} liveSteps={[]} isStreaming={false} error={null} onSubmit={vi.fn()} />);

    expect(screen.getByText("Try starting with")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Help me think through whether to rewrite/ }),
    ).toBeInTheDocument();
  });

  it("loads a picked example into the composer", async () => {
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} liveSteps={[]} isStreaming={false} error={null} onSubmit={vi.fn()} />);

    await user.click(
      screen.getByRole("button", { name: /I have a vague idea for a note-taking app/ }),
    );

    expect(screen.getByPlaceholderText("What's on your mind?")).toHaveValue(
      "I have a vague idea for a note-taking app and want to sharpen it.",
    );
  });

  it("shows a skeleton and hides the transcript while history loads", () => {
    render(
      <ChatPanel
        messages={[{ role: "user", content: "earlier message" }]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        historyLoading
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByText("earlier message")).not.toBeInTheDocument();
  });

  it("renders assistant messages as Markdown but leaves user text literal", () => {
    render(
      <ChatPanel
        messages={[
          { role: "user", content: "look at **this** and `that`" },
          { role: "assistant", content: "Here is a point:\n\n- **bold** item\n- [a link](https://example.com)" },
        ]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    // User text is not parsed as Markdown.
    expect(screen.getByText("look at **this** and `that`")).toBeInTheDocument();

    // Assistant text is.
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    const link = screen.getByRole("link", { name: "a link" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("keeps a collapsed activity trail on a finished assistant turn", () => {
    render(
      <ChatPanel
        messages={[
          {
            role: "assistant",
            content: "Done.",
            steps: ["Searching the web", "Weighing tradeoffs"],
            durationMs: 4200,
          },
        ]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText(/Worked for 4s · 2 steps/)).toBeInTheDocument();
    expect(screen.getByText("Weighing tradeoffs")).toBeInTheDocument();
    // The live-chip cluster is not what's rendering this.
    expect(screen.queryByTestId("live-step")).not.toBeInTheDocument();
  });

  it("renders the reply as it streams, with a caret", () => {
    const { container } = render(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        streamingText="Here's where I've la"
        isStreaming
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("Here's where I've la")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    // The generic "Thinking" placeholder line gives way to the streaming text.
    expect(container.querySelector(".animate-bounce")).not.toBeInTheDocument();
  });

  it("marks an aborted turn as stopped early", () => {
    render(
      <ChatPanel
        messages={[{ role: "assistant", content: "partial answer", stopped: true }]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("partial answer")).toBeInTheDocument();
    expect(screen.getByText("Stopped early.")).toBeInTheDocument();
  });

  it("renders an error banner", () => {
    render(
      <ChatPanel messages={[]} liveSteps={[]} isStreaming={false} error="graph blew up" onSubmit={vi.fn()} />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("graph blew up");
  });

  it("disables sending while a turn is streaming", () => {
    render(<ChatPanel messages={[]} liveSteps={[]} isStreaming error={null} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Thinking…" })).toBeDisabled();
  });

  it("disables the attach control until a session exists", () => {
    const onUploadFile = vi.fn();
    const { rerender } = render(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
        onUploadFile={onUploadFile}
        canAttach={false}
      />,
    );
    expect(screen.getByRole("button", { name: "Attach a file" })).toBeDisabled();

    rerender(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
        onUploadFile={onUploadFile}
        canAttach
      />,
    );
    expect(screen.getByRole("button", { name: "Attach a file" })).toBeEnabled();
  });

  it("uploads a chosen file and shows it in the attachment strip", async () => {
    const onUploadFile = vi
      .fn()
      .mockResolvedValue({ id: "d1", title: "notes.md", content: "" });
    const { container } = render(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
        onUploadFile={onUploadFile}
        canAttach
      />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["# hi"], "notes.md", { type: "text/markdown" });
    fireEvent.change(input, { target: { files: [file] } });

    expect(onUploadFile).toHaveBeenCalledWith(file);
    expect(await screen.findByText("notes.md")).toBeInTheDocument();
  });

  it("rejects an unsupported file type without calling the uploader", () => {
    const onUploadFile = vi.fn();
    const { container } = render(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        isStreaming={false}
        error={null}
        onSubmit={vi.fn()}
        onUploadFile={onUploadFile}
        canAttach
      />,
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["x"], "malware.exe")] },
    });

    expect(onUploadFile).not.toHaveBeenCalled();
    expect(screen.getByText(/PDF, text, or Markdown only/)).toBeInTheDocument();
  });

  it("shows a Stop button while streaming and calls onStop when clicked", async () => {
    const user = userEvent.setup();
    const onStop = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        liveSteps={[]}
        isStreaming
        error={null}
        onSubmit={vi.fn()}
        onStop={onStop}
      />,
    );

    expect(screen.queryByRole("button", { name: "Thinking…" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalledOnce();
  });
});
