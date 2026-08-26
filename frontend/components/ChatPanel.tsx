"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { ThinkingMode } from "@/lib/types";
import { modeStyle } from "@/lib/modes";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  question?: string;
}

export interface LiveStep {
  node: string;
  mode: ThinkingMode | null;
}

export default function ChatPanel({
  messages,
  liveSteps,
  isStreaming,
  error,
  onSubmit,
}: {
  messages: ChatMessage[];
  liveSteps: LiveStep[];
  isStreaming: boolean;
  error: string | null;
  onSubmit: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft("");
    onSubmit(text);
  };

  return (
    <div className="flex min-h-[520px] flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">
            Tell me what you&apos;re thinking through, and I&apos;ll help you frame it.
          </p>
        ) : null}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              message.role === "user"
                ? "ml-auto bg-[var(--mode-accent-soft)] text-[var(--text)]"
                : "bg-[var(--surface-raised)] text-[var(--text)]"
            }`}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
            {message.question ? (
              <p className="mt-1 text-[var(--text-muted)]">{message.question}</p>
            ) : null}
          </div>
        ))}

        <AnimatePresence>
          {liveSteps.map((step, index) => (
            <motion.div
              key={`${step.node}-${index}`}
              data-testid="live-step"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-muted)]"
              style={step.mode ? { color: modeStyle(step.mode).accent } : undefined}
            >
              {step.node}
            </motion.div>
          ))}
        </AnimatePresence>

        {error ? (
          <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        ) : null}
      </div>

      <div className="flex gap-2 border-t border-[var(--border)] p-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="What's on your mind?"
          rows={2}
          className="flex-1 resize-none rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--mode-accent)]"
        />
        <button
          type="button"
          onClick={submit}
          disabled={isStreaming || !draft.trim()}
          className="rounded-lg bg-[var(--mode-accent)] px-4 py-2 text-sm font-medium text-black disabled:opacity-40"
        >
          {isStreaming ? "Thinking…" : "Send"}
        </button>
      </div>
    </div>
  );
}
