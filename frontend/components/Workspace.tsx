"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getProject, listProjects, streamTurn } from "@/lib/api-client";
import type { ProjectState, ProjectSummary, ThinkingMode } from "@/lib/types";
import ChatPanel, { type ChatMessage, type LiveStep } from "./ChatPanel";
import ModeIndicator from "./ModeIndicator";
import SessionSelector from "./SessionSelector";
import NorthStarCard from "./workspace-panels/NorthStarCard";
import BranchGraph from "./workspace-panels/BranchGraph";
import EvidenceTimeline from "./workspace-panels/EvidenceTimeline";
import DecisionHistory from "./workspace-panels/DecisionHistory";
import NextActionsPanel from "./workspace-panels/NextActionsPanel";

export default function Workspace({
  initialProjectId,
}: {
  initialProjectId: string | null;
}) {
  const router = useRouter();
  const [projectId, setProjectId] = useState<string | null>(initialProjectId);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [liveSteps, setLiveSteps] = useState<LiveStep[]>([]);
  const [liveMode, setLiveMode] = useState<ThinkingMode | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = useCallback(() => {
    listProjects().then(setProjects).catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!projectId) {
      setProjectState(null);
      return;
    }
    getProject(projectId).then(setProjectState).catch(() => setProjectState(null));
  }, [projectId]);

  const handleSelectSession = useCallback(
    (id: string) => {
      setMessages([]);
      setProjectId(id);
      router.push(`/session/${id}`);
    },
    [router],
  );

  const handleNewSession = useCallback(() => {
    setMessages([]);
    setProjectId(null);
    setProjectState(null);
    router.push("/");
  }, [router]);

  const handleSubmit = useCallback(
    async (text: string) => {
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setLiveSteps([]);
      setIsStreaming(true);

      try {
        for await (const event of streamTurn(text, projectId)) {
          if (event.type === "node") {
            setLiveSteps((prev) => [...prev, { node: event.node, mode: event.mode }]);
            if (event.mode) {
              setLiveMode(event.mode);
            }
          } else if (event.type === "turn" && event.turn) {
            const turn = event.turn;
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: turn.message, question: turn.question },
            ]);
            setLiveSteps([]);
            setLiveMode(null);

            if (!projectId) {
              setProjectId(turn.project_id);
              // Plain History API, not `router.replace`: the latter would
              // navigate from the `/` route component to the
              // `/session/[projectId]` one, remounting `Workspace` and
              // discarding the messages/mode state this turn just produced.
              // This only needs to sync the address bar for reload/share.
              window.history.replaceState(null, "", `/session/${turn.project_id}`);
            }
            getProject(turn.project_id).then(setProjectState).catch(() => undefined);
            refreshProjects();
          } else if (event.type === "error") {
            setError(event.detail || "Something went wrong while thinking.");
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        setIsStreaming(false);
      }
    },
    [projectId, refreshProjects, router],
  );

  const displayedMode = liveMode ?? projectState?.current_mode ?? "capture";

  return (
    <div className="mx-auto flex min-h-screen max-w-[1400px] flex-col gap-4 p-4 lg:p-6">
      <header className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-tight">MyThinking</h1>
          <ModeIndicator mode={displayedMode} />
        </div>
        <SessionSelector
          projects={projects}
          currentProjectId={projectId}
          onSelect={handleSelectSession}
          onNewSession={handleNewSession}
        />
      </header>

      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <ChatPanel
          messages={messages}
          liveSteps={liveSteps}
          isStreaming={isStreaming}
          error={error}
          onSubmit={handleSubmit}
        />

        <div className="flex flex-col gap-4">
          <NorthStarCard northStar={projectState?.north_star ?? null} />
          <BranchGraph branches={projectState?.branches ?? []} />
          <EvidenceTimeline evidence={projectState?.evidence ?? []} />
          <DecisionHistory decisions={projectState?.decisions ?? []} />
          <NextActionsPanel nextActions={projectState?.next_actions ?? []} />
        </div>
      </div>
    </div>
  );
}
