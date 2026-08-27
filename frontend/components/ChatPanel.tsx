"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { ResearchDocument, ThinkingMode } from "@/lib/types";
import { MODE_STYLES, modeStyle } from "@/lib/modes";
import { stepLabel } from "@/lib/step-labels";
import { UPLOAD_ACCEPT, useDocumentUpload } from "@/lib/use-document-upload";
import Icon from "./Icon";
import Markdown from "./Markdown";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  question?: string;
  /** Humanised tool steps the agent ran to produce this reply (assistant only). */
  steps?: string[];
  /** Wall-clock the turn took, ms. */
  durationMs?: number;
  /** The turn was aborted by the user before it finished. */
  stopped?: boolean;
  /** A UI-generated system line (e.g. "Stopped."), not a model reply. */
  notice?: boolean;
}

export interface LiveStep {
  node: string;
  mode: ThinkingMode | null;
}

const EXAMPLE_PROMPTS = [
  "Help me think through whether to rewrite our billing service.",
  "I have a vague idea for a note-taking app and want to sharpen it.",
  "Challenge my assumption that we need to hire before shipping.",
];

const DRAFT_KEY = "mythinking:composer-draft";

const MODE_ORDER: ThinkingMode[] = [
  "capture",
  "clarify",
  "challenge",
  "explore",
  "research",
  "converge",
  "decide",
];

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="space-y-5">
      <p className="text-sm text-[var(--text-muted)]">
        Tell me what you&apos;re thinking through, and I&apos;ll help you frame it, pressure-test
        it, and turn it into a plan. The panel on the right fills in as we go.
      </p>

      <div className="space-y-2">
        <p className="text-xs font-medium text-[var(--text-muted)]">Try starting with</p>
        <div className="flex flex-col gap-1.5">
          {EXAMPLE_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onPick(prompt)}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-left text-sm text-[var(--text)] hover:border-[var(--mode-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-[var(--text-muted)]">
          The modes I move through
        </p>
        <div className="flex flex-wrap gap-1.5">
          {MODE_ORDER.map((mode) => {
            const style = MODE_STYLES[mode];
            return (
              <span
                key={mode}
                className="rounded-full border px-2 py-0.5 text-xs"
                style={{ borderColor: style.accent, color: style.accent }}
                title={style.description}
              >
                {style.label}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * The persistent record of what the agent did on a completed turn. During the
 * turn the same steps stream as live chips; afterwards they collapse to one
 * line under the reply so the transparency isn't lost.
 */
function ActivityTrail({ steps, durationMs }: { steps: string[]; durationMs?: number }) {
  if (steps.length === 0) return null;
  const secs = durationMs ? Math.max(1, Math.round(durationMs / 1000)) : null;
  const summary =
    `Worked${secs ? ` for ${secs}s` : ""} · ${steps.length} step${steps.length === 1 ? "" : "s"}`;
  return (
    <details className="group mt-2 border-t border-[var(--border)] pt-1.5 text-xs text-[var(--text-muted)]">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 select-none">
        <Icon
          name="chevron-right"
          size={12}
          className="shrink-0 transition-transform group-open:rotate-90"
        />
        {summary}
      </summary>
      <ol className="mt-1.5 space-y-1 border-l border-[var(--border)] pl-3">
        {steps.map((label, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-[var(--text-muted)] opacity-60">{i + 1}.</span>
            <span>{label}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable — nothing to do */
        }
      }}
      className="absolute right-1 top-1 rounded border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 text-[10px] text-[var(--text-muted)] opacity-0 transition-opacity hover:text-[var(--text)] focus-visible:opacity-100 group-hover:opacity-100"
      aria-label="Copy message"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {[
        { w: "60%", me: true },
        { w: "85%", me: false },
        { w: "45%", me: true },
      ].map((row, i) => (
        <div
          key={i}
          className={`h-10 animate-pulse rounded-lg bg-[var(--surface-raised)] ${row.me ? "ml-auto" : ""}`}
          style={{ width: row.w }}
        />
      ))}
    </div>
  );
}

export default function ChatPanel({
  messages,
  liveSteps,
  streamingText = "",
  isStreaming,
  error,
  historyLoading = false,
  prefill = null,
  onSubmit,
  onStop,
  onUploadFile,
  canAttach = false,
}: {
  messages: ChatMessage[];
  liveSteps: LiveStep[];
  streamingText?: string;
  isStreaming: boolean;
  error: string | null;
  historyLoading?: boolean;
  prefill?: { text: string; nonce: number } | null;
  onSubmit: (text: string) => void;
  onStop?: () => void;
  /** Upload one file to the session's document store; resolves with the stored doc. */
  onUploadFile?: (file: File) => Promise<ResearchDocument>;
  /** Whether attaching is possible yet (a session must exist first). */
  canAttach?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const attachEnabled = Boolean(onUploadFile && canAttach);
  const {
    items: attachments,
    upload: uploadFiles,
    dismiss: dismissAttachment,
  } = useDocumentUpload(onUploadFile);

  // Persist the composer draft so an accidental reload mid-thought doesn't lose
  // it. Restored once on mount; cleared the moment the draft empties (on submit).
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(DRAFT_KEY);
      if (saved) setDraft(saved);
    } catch {
      /* storage unavailable — nothing to restore */
    }
  }, []);
  useEffect(() => {
    try {
      if (draft) window.localStorage.setItem(DRAFT_KEY, draft);
      else window.localStorage.removeItem(DRAFT_KEY);
    } catch {
      /* storage unavailable — skip persistence */
    }
  }, [draft]);
  // Whether the transcript is scrolled to (near) the bottom. Only then does new
  // content auto-scroll — otherwise reading back history isn't interrupted.
  const [pinned, setPinned] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft("");
    onSubmit(text);
  };

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  // Auto-follow new content only when the user is already at the bottom.
  useEffect(() => {
    if (pinned) scrollToBottom();
  }, [messages, liveSteps, streamingText, isStreaming, historyLoading, pinned]);

  // A workspace panel asked to stage a message (e.g. "Approve this direction").
  // We fill the composer and focus it rather than sending, so committing stays a
  // deliberate keystroke.
  useEffect(() => {
    if (!prefill) return;
    // Don't clobber an in-progress message: if the user was already typing
    // something else, append the staged text on a new line instead of replacing.
    setDraft((cur) => {
      const trimmed = cur.trim();
      return trimmed && trimmed !== prefill.text.trim()
        ? `${trimmed}\n\n${prefill.text}`
        : prefill.text;
    });
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
      }
    });
  }, [prefill]);

  // Auto-grow the composer up to a ceiling, then let it scroll.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [draft]);

  // Elapsed-time counter so a long think doesn't look like a hang.
  useEffect(() => {
    if (!isStreaming) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, [isStreaming]);

  const showThinking = isStreaming && liveSteps.length === 0 && !streamingText;

  return (
    <div
      className="relative flex min-h-[520px] flex-1 flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] lg:min-h-0"
      onDragEnter={(e) => {
        if (!attachEnabled || !e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(e) => {
        if (attachEnabled && e.dataTransfer.types.includes("Files")) e.preventDefault();
      }}
      onDragLeave={() => {
        if (!attachEnabled) return;
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setDragging(false);
      }}
      onDrop={(e) => {
        if (!attachEnabled) return;
        e.preventDefault();
        dragDepth.current = 0;
        setDragging(false);
        if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
      }}
    >
      {dragging ? (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-[var(--mode-accent)] bg-[var(--bg)]/85 text-sm font-medium text-[var(--text)]">
          Drop to attach — PDF, text, or Markdown
        </div>
      ) : null}
      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
        }}
        className="flex-1 space-y-3 overflow-y-auto p-4"
        aria-busy={isStreaming || historyLoading}
      >
        {historyLoading ? (
          <HistorySkeleton />
        ) : messages.length === 0 ? (
          <EmptyState
            onPick={(text) => {
              setDraft(text);
              textareaRef.current?.focus();
            }}
          />
        ) : null}

        {!historyLoading &&
          messages.map((message, index) =>
            message.notice ? (
              <p key={index} className="py-1 text-center text-xs text-[var(--text-muted)]">
                {message.content}
              </p>
            ) : (
              <div key={index} className={message.role === "user" ? "flex justify-end" : ""}>
                <div
                  className={`group relative max-w-[85%] rounded-lg py-2 text-sm ${
                    message.role === "user"
                      ? "bg-[var(--mode-accent-soft)] px-3 text-[var(--text)]"
                      : "bg-[var(--surface-raised)] pl-3 pr-9 text-[var(--text)]"
                  }`}
                >
                  {message.role === "assistant" ? (
                    <>
                      <Markdown>{message.content}</Markdown>
                      <CopyButton text={message.content} />
                    </>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                  {message.question ? (
                    <p
                      className="mt-2 border-l-2 border-[var(--mode-accent)] pl-2 text-[var(--text)]"
                    >
                      {message.question}
                    </p>
                  ) : null}
                  {message.role === "assistant" && message.steps?.length ? (
                    <ActivityTrail steps={message.steps} durationMs={message.durationMs} />
                  ) : null}
                  {message.stopped ? (
                    <p className="mt-1 text-xs italic text-[var(--text-muted)]">Stopped early.</p>
                  ) : null}
                </div>
              </div>
            ),
          )}

        {streamingText ? (
          <div aria-live="polite">
            <div className="max-w-[85%] rounded-lg bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text)]">
              <Markdown>{streamingText}</Markdown>
              <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-[var(--mode-accent)]" />
            </div>
          </div>
        ) : null}

        {isStreaming ? (
          <AnimatePresence>
            {liveSteps.map((step, index) => (
              <motion.div
                key={`${step.node}-${index}`}
                data-testid="live-step"
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.12 }}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-muted)]"
                style={step.mode ? { color: modeStyle(step.mode).accent } : undefined}
              >
                {stepLabel(step.node)}
              </motion.div>
            ))}
          </AnimatePresence>
        ) : null}

        {showThinking ? (
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <span className="flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--text-muted)] [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--text-muted)] [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--text-muted)]" />
            </span>
            Thinking{elapsed > 2 ? ` · ${elapsed}s` : ""}
          </div>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
          >
            {error}
          </p>
        ) : null}
      </div>

      {!pinned ? (
        <button
          type="button"
          onClick={() => {
            scrollToBottom();
            setPinned(true);
          }}
          className="absolute bottom-24 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1 text-xs text-[var(--text)] shadow-lg hover:border-[var(--mode-accent)]"
        >
          Jump to latest
          <Icon name="arrow-down" size={12} />
        </button>
      ) : null}

      {attachments.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5 border-t border-[var(--border)] px-3 pt-2">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-2 py-1 text-xs"
            >
              <Icon
                name={
                  a.status === "uploading"
                    ? "spinner"
                    : a.status === "done"
                      ? "file"
                      : "alert"
                }
                size={13}
                className={
                  a.status === "error"
                    ? "text-red-300"
                    : "text-[var(--text-muted)]"
                }
              />
              <span className="max-w-[18ch] truncate" title={a.name}>
                {a.name}
              </span>
              {a.status === "error" && a.error ? (
                <span className="text-red-300">— {a.error}</span>
              ) : null}
              {a.status !== "uploading" ? (
                <button
                  type="button"
                  onClick={() => dismissAttachment(a.id)}
                  aria-label={`Dismiss ${a.name}`}
                  className="rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                >
                  <Icon name="close" size={12} />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="border-t border-[var(--border)] p-3">
        <div className="flex gap-2">
          {onUploadFile ? (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept={UPLOAD_ACCEPT}
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.length) uploadFiles(e.target.files);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={!attachEnabled}
                aria-label="Attach a file"
                title={
                  attachEnabled
                    ? "Attach a file (PDF, text, Markdown)"
                    : "Send a message first to start the session, then attach files"
                }
                className="h-fit self-end rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2.5 text-[var(--text-muted)] hover:border-[var(--mode-accent)] hover:text-[var(--text)] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
              >
                <Icon name="paperclip" />
              </button>
            </>
          ) : null}
          <textarea
            ref={textareaRef}
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
          {isStreaming && onStop ? (
            <button
              type="button"
              onClick={onStop}
              className="h-fit self-end rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-2 text-sm font-medium text-[var(--text)] hover:border-[var(--mode-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={isStreaming || !draft.trim()}
              className="h-fit self-end rounded-lg bg-[var(--mode-accent)] px-4 py-2 text-sm font-medium text-black disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
            >
              {isStreaming ? "Thinking…" : "Send"}
            </button>
          )}
        </div>
        <p className="mt-1.5 text-xs text-[var(--text-muted)]">
          <kbd className="rounded border border-[var(--border)] px-1">Enter</kbd> to send ·{" "}
          <kbd className="rounded border border-[var(--border)] px-1">Shift</kbd>+
          <kbd className="rounded border border-[var(--border)] px-1">Enter</kbd> for a new line
        </p>
      </div>
    </div>
  );
}
