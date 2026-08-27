"use client";

import { Component, type ReactNode } from "react";

interface Props {
  /** Shown in place of the subtree when it throws. */
  label: string;
  onReset?: () => void;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Contains a render/runtime failure to one region. Before this, a throw in any
 * workspace panel took down the whole page — losing the conversation with it.
 * Wrapped around the rail so the chat survives a bad panel, and vice versa.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error);
  }

  private reset = () => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200"
        >
          <p className="font-medium">{this.props.label}</p>
          <p className="mt-1 text-xs text-red-300/80">{this.state.error.message}</p>
          <button
            type="button"
            onClick={this.reset}
            className="mt-3 rounded-md border border-red-400/50 px-2 py-1 text-xs font-medium text-red-100 hover:bg-red-500/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
