import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

  it("renders live thinking steps while streaming", () => {
    render(
      <ChatPanel
        messages={[]}
        liveSteps={[{ node: "capture", mode: null }, { node: "choose_mode", mode: "clarify" }]}
        isStreaming
        error={null}
        onSubmit={vi.fn()}
      />,
    );

    const steps = screen.getAllByTestId("live-step");
    expect(steps).toHaveLength(2);
    expect(steps[1]).toHaveTextContent("choose_mode");
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
});
