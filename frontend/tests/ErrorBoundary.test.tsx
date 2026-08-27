import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorBoundary from "@/components/ErrorBoundary";

function Boom({ crash }: { crash: boolean }) {
  if (crash) throw new Error("panel exploded");
  return <p>healthy content</p>;
}

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary label="panel failed">
        <Boom crash={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("healthy content")).toBeInTheDocument();
  });

  it("shows the fallback with the label and error message when a child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <ErrorBoundary label="panel failed">
        <Boom crash />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("panel failed");
    expect(screen.getByRole("alert")).toHaveTextContent("panel exploded");
    spy.mockRestore();
  });

  it("calls onReset when the user clicks Try again", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(
      <ErrorBoundary label="panel failed" onReset={onReset}>
        <Boom crash />
      </ErrorBoundary>,
    );

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onReset).toHaveBeenCalledOnce();
    spy.mockRestore();
  });
});
