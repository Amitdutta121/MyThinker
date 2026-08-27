"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import {
  deleteDocument,
  deleteDocuments,
  getDocuments,
  getMessages,
  getProject,
  listProjects,
  streamTurn,
  uploadDocument,
} from "@/lib/api-client";
import { modeStyle } from "@/lib/modes";
import { stepLabel } from "@/lib/step-labels";
import { summarizeStateChange } from "@/lib/state-diff";
import type {
  ProjectState,
  ProjectSummary,
  ResearchDocument,
  ThinkingMode,
} from "@/lib/types";
import ChatPanel, { type ChatMessage, type LiveStep } from "./ChatPanel";
import ErrorBoundary from "./ErrorBoundary";
import ModeIndicator from "./ModeIndicator";
import SessionSelector from "./SessionSelector";
import SourcesPanel from "./SourcesPanel";
import RightPanel from "./panel/RightPanel";

type LoadStatus = "idle" | "loading" | "ready" | "error";

export default function Workspace({
  initialProjectId,
}: {
  initialProjectId: string | null;
}) {
  const router = useRouter();
  const [projectId, setProjectId] = useState<string | null>(initialProjectId);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [documents, setDocuments] = useState<ResearchDocument[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionStatus, setSessionStatus] = useState<LoadStatus>(
    initialProjectId ? "loading" : "idle",
  );
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<LiveStep[]>([]);
  const [liveMode, setLiveMode] = useState<ThinkingMode | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Transient "what changed on the board this turn" summary (see state-diff).
  const [boardChange, setBoardChange] = useState<string[]>([]);

  // Bumped on every session load so a slow response for a session the user has
  // already navigated away from can't overwrite the current one.
  const loadSeq = useRef(0);

  // Latest project state, readable from `handleSubmit` without stale-closure
  // risk (the callback isn't recreated when `projectState` changes).
  const projectStateRef = useRef<ProjectState | null>(null);
  useEffect(() => {
    projectStateRef.current = projectState;
  }, [projectState]);

  // The change ribbon persists until the next turn replaces it (or the user
  // dismisses it) — a 12s auto-hide meant it vanished while you were still
  // reading the reply that caused the change.

  // Lets the user abort an in-flight turn from the composer.
  const abortRef = useRef<AbortController | null>(null);

  const refreshProjects = useCallback(() => {
    listProjects().then(setProjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  const loadSession = useCallback((id: string) => {
    const seq = ++loadSeq.current;
    setSessionStatus("loading");
    setSessionError(null);

    Promise.all([getProject(id), getMessages(id), getDocuments(id).catch(() => [])])
      .then(([state, transcript, docs]) => {
        if (seq !== loadSeq.current) return;
        if (!state) {
          setSessionStatus("error");
          setSessionError("This session could not be found.");
          return;
        }
        setProjectState(state);
        setDocuments(docs);
        setMessages(
          transcript.map((m) => ({ role: m.role, content: m.content })),
        );
        setSessionStatus("ready");
      })
      .catch((err) => {
        if (seq !== loadSeq.current) return;
        setSessionStatus("error");
        setSessionError(
          err instanceof Error ? err.message : "Could not load this session.",
        );
      });
  }, []);

  useEffect(() => {
    setBoardChange([]);
    if (!projectId) {
      loadSeq.current++;
      setProjectState(null);
      setDocuments([]);
      setMessages([]);
      setSessionStatus("idle");
      setSessionError(null);
      return;
    }
    loadSession(projectId);
  }, [projectId, loadSession]);

  const handleSelectSession = useCallback(
    (id: string) => {
      if (id === projectId) return;
      setProjectId(id);
      router.push(`/session/${id}`);
    },
    [projectId, router],
  );

  const handleNewSession = useCallback(() => {
    setProjectId(null);
    router.push("/");
  }, [router]);

  // A panel can push text into the composer (e.g. "Approve this direction" on the
  // proposal card). `nonce` forces the effect to re-run even for the same text.
  const [prefill, setPrefill] = useState<{ text: string; nonce: number } | null>(null);
  const prefillComposer = useCallback((text: string) => {
    setPrefill({ text, nonce: Date.now() });
  }, []);

  const handleSubmit = useCallback(
    async (text: string) => {
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setLiveSteps([]);
      setBoardChange([]);
      setStreamingText("");
      setIsStreaming(true);

      const preTurnState = projectStateRef.current;

      const controller = new AbortController();
      abortRef.current = controller;
      const startedAt = Date.now();
      const stepsThisTurn: string[] = [];
      let streamed = "";

      try {
        for await (const event of streamTurn(text, projectId, controller.signal)) {
          if (event.type === "node") {
            stepsThisTurn.push(stepLabel(event.node));
            setLiveSteps((prev) => [...prev, { node: event.node, mode: event.mode }]);
            if (event.mode) {
              setLiveMode(event.mode);
            }
            // Any text streamed before a tool ran was the model deciding to
            // act, not its answer — drop it and stream the real reply fresh.
            streamed = "";
            setStreamingText("");
          } else if (event.type === "token") {
            streamed += event.detail || "";
            setStreamingText(streamed);
          } else if (event.type === "turn" && event.turn) {
            const turn = event.turn;
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: turn.message,
                question: turn.question,
                steps: stepsThisTurn.slice(),
                durationMs: Date.now() - startedAt,
              },
            ]);
            setStreamingText("");
            setLiveSteps([]);
            // `liveMode` is cleared only once the refreshed project state is in
            // hand (below), so `displayedMode` never flickers back to the stale
            // pre-turn mode between the turn event and the state refresh.

            if (!projectId) {
              setProjectId(turn.project_id);
              // Plain History API, not `router.replace`: the latter would
              // navigate from the `/` route component to the
              // `/session/[projectId]` one, remounting `Workspace` and
              // discarding the messages/mode state this turn just produced.
              // This only needs to sync the address bar for reload/share.
              window.history.replaceState(null, "", `/session/${turn.project_id}`);
            }
            getProject(turn.project_id)
              .then((next) => {
                if (!next) return;
                setProjectState(next);
                setBoardChange(summarizeStateChange(preTurnState, next));
              })
              .catch(() => undefined)
              .finally(() => setLiveMode(null));
            getDocuments(turn.project_id).then(setDocuments).catch(() => undefined);
            refreshProjects();
          } else if (event.type === "error") {
            setError(event.detail || "Something went wrong while thinking.");
            setStreamingText("");
            setLiveSteps([]);
            setLiveMode(null);
          }
        }
      } catch (err) {
        // A user-initiated abort is a clean stop, not a failure: keep whatever
        // text had streamed so far, marked as cut short.
        if (err instanceof DOMException && err.name === "AbortError") {
          setMessages((prev) => [
            ...prev,
            streamed.trim()
              ? {
                  role: "assistant",
                  content: streamed,
                  steps: stepsThisTurn.slice(),
                  durationMs: Date.now() - startedAt,
                  stopped: true,
                }
              : { role: "assistant", content: "Stopped.", notice: true },
          ]);
        } else {
          setError(err instanceof Error ? err.message : "Something went wrong.");
        }
        setStreamingText("");
        setLiveSteps([]);
        setLiveMode(null);
      } finally {
        abortRef.current = null;
        setIsStreaming(false);
      }
    },
    [projectId, refreshProjects],
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // Attach a file to the current session's document store. Requires an existing
  // project (the composer disables the control until the first turn creates one).
  const handleUploadFile = useCallback(
    async (file: File): Promise<ResearchDocument> => {
      if (!projectId) {
        throw new Error("Send a message first to start the session, then attach files.");
      }
      const doc = await uploadDocument(projectId, file);
      getDocuments(projectId)
        .then(setDocuments)
        .catch(() => undefined);
      return doc;
    },
    [projectId],
  );

  // Remove one stored source. Optimistic: drop the row immediately, restore the
  // pre-delete list if the request fails.
  const handleDeleteDocument = useCallback(
    async (id: string) => {
      if (!projectId) return;
      let snapshot: ResearchDocument[] = [];
      setDocuments((docs) => {
        snapshot = docs;
        return docs.filter((d) => d.id !== id);
      });
      try {
        setDocuments(await deleteDocument(projectId, id));
      } catch {
        setDocuments(snapshot);
      }
    },
    [projectId],
  );

  // Remove several stored sources at once (multi-select). Same optimistic
  // pattern as the single delete.
  const handleDeleteDocuments = useCallback(
    async (ids: string[]) => {
      if (!projectId || ids.length === 0) return;
      const drop = new Set(ids);
      let snapshot: ResearchDocument[] = [];
      setDocuments((docs) => {
        snapshot = docs;
        return docs.filter((d) => !drop.has(d.id ?? ""));
      });
      try {
        setDocuments(await deleteDocuments(projectId, ids));
      } catch {
        setDocuments(snapshot);
      }
    },
    [projectId],
  );

  const displayedMode = liveMode ?? projectState?.current_mode ?? "capture";
  const sessionLoading = sessionStatus === "loading";
  const [mobileView, setMobileView] = useState<"sources" | "chat" | "board">("chat");
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);

  const tint = modeStyle(displayedMode);
  const tintStyle = {
    "--mode-accent": tint.accent,
    "--mode-accent-soft": tint.accentSoft,
  } as CSSProperties;

  const sessionTitle = projectState?.north_star?.title?.trim() || "";
  useEffect(() => {
    document.title = sessionTitle ? `${sessionTitle} · MyThinking` : "MyThinking";
  }, [sessionTitle]);

  return (
    <div
      className="mode-tint mx-auto flex min-h-screen max-w-[1600px] flex-col gap-4 p-4 lg:h-screen lg:min-h-0 lg:overflow-hidden lg:p-6"
      style={tintStyle}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-sm font-semibold tracking-tight text-[var(--text-muted)]">
            MyThinking
          </span>
          <h1 className="max-w-[42ch] truncate text-lg font-semibold tracking-tight">
            {sessionTitle || "New session"}
          </h1>
          {/* A mode badge on an untouched new session asserts state that doesn't
              exist yet — only show it once the session is underway. */}
          {projectId || projectState || messages.length > 0 ? (
            <ModeIndicator mode={displayedMode} />
          ) : null}
        </div>
        <SessionSelector
          projects={projects}
          currentProjectId={projectId}
          onSelect={handleSelectSession}
          onNewSession={handleNewSession}
        />
      </header>

      {sessionError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          <span>{sessionError}</span>
          {projectId ? (
            <button
              type="button"
              onClick={() => loadSession(projectId)}
              className="shrink-0 rounded-md border border-red-400/50 px-2 py-1 text-xs font-medium text-red-100 hover:bg-red-500/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : null}

      <div
        role="tablist"
        aria-label="Workspace view"
        className="flex gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 text-sm lg:hidden"
      >
        {(["sources", "chat", "board"] as const).map((view) => (
          <button
            key={view}
            type="button"
            role="tab"
            aria-selected={mobileView === view}
            onClick={() => setMobileView(view)}
            className={`flex-1 rounded-md px-3 py-1.5 ${
              mobileView === view
                ? "bg-[var(--surface-raised)] text-[var(--text)]"
                : "text-[var(--text-muted)]"
            }`}
          >
            {view === "sources" ? "Sources" : view === "chat" ? "Conversation" : "Board"}
          </button>
        ))}
      </div>

      <main
        className={`grid flex-1 grid-cols-1 gap-4 lg:min-h-0 ${
          sourcesCollapsed
            ? "lg:grid-cols-[52px_minmax(0,1.15fr)_minmax(0,0.9fr)]"
            : "lg:grid-cols-[260px_minmax(0,1.15fr)_minmax(0,0.9fr)]"
        }`}
      >
        <div
          className={`lg:min-h-0 lg:h-full ${
            mobileView === "sources" ? "block" : "hidden lg:block"
          }`}
        >
          <ErrorBoundary label="The sources panel hit an error.">
            <SourcesPanel
              documents={documents}
              onUploadFile={handleUploadFile}
              onDeleteDocument={projectId ? handleDeleteDocument : undefined}
              onDeleteDocuments={projectId ? handleDeleteDocuments : undefined}
              canAttach={Boolean(projectId)}
              loading={sessionLoading}
              collapsed={sourcesCollapsed}
              onToggleCollapse={() => setSourcesCollapsed((v) => !v)}
            />
          </ErrorBoundary>
        </div>

        <div
          className={`lg:min-h-0 lg:h-full ${
            mobileView === "chat" ? "flex flex-col" : "hidden lg:flex lg:flex-col"
          }`}
        >
          <ErrorBoundary label="The conversation panel hit an error.">
            <ChatPanel
              messages={messages}
              liveSteps={liveSteps}
              streamingText={streamingText}
              isStreaming={isStreaming}
              error={error}
              historyLoading={sessionLoading}
              prefill={prefill}
              onSubmit={handleSubmit}
              onStop={handleStop}
              onUploadFile={handleUploadFile}
              canAttach={Boolean(projectId)}
            />
          </ErrorBoundary>
        </div>

        <div
          className={`lg:min-h-0 lg:h-full lg:overflow-y-auto lg:pr-1 ${
            mobileView === "board" ? "block" : "hidden lg:block"
          }`}
        >
          <ErrorBoundary
            key={projectId ?? "new"}
            label="The board couldn't be rendered."
            onReset={() => projectId && loadSession(projectId)}
          >
            <RightPanel
              projectState={projectState}
              loading={sessionLoading}
              change={boardChange}
              onDismissChange={() => setBoardChange([])}
              onPrefillComposer={prefillComposer}
              onStateChange={setProjectState}
            />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
