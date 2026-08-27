"use client";

import { useEffect, useRef, useState } from "react";
import type { ResearchDocument } from "@/lib/types";
import { UPLOAD_ACCEPT, useDocumentUpload } from "@/lib/use-document-upload";
import Icon from "./Icon";

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function isWebSource(doc: ResearchDocument): boolean {
  return /^https?:\/\//i.test(doc.source_url ?? "");
}

function wordCount(text: string | undefined): number {
  return text ? Math.max(1, Math.round(text.length / 5)) : 0;
}

/**
 * The managed source list — left column, NotebookLM-style. Adds files to the
 * session's document store (which makes them citable in the conversation) and
 * lets the user open any stored source to read its extracted text.
 */
export default function SourcesPanel({
  documents,
  onUploadFile,
  onDeleteDocument,
  onDeleteDocuments,
  canAttach = false,
  loading = false,
  collapsed = false,
  onToggleCollapse,
}: {
  documents: ResearchDocument[];
  onUploadFile?: (file: File) => Promise<ResearchDocument>;
  onDeleteDocument?: (id: string) => void;
  onDeleteDocuments?: (ids: string[]) => void;
  canAttach?: boolean;
  loading?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<ResearchDocument | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(() => new Set());
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [dragging, setDragging] = useState(false);
  const { items, upload, dismiss } = useDocumentUpload(onUploadFile);

  const canAdd = Boolean(onUploadFile && canAttach);
  const canMultiSelect = Boolean(onDeleteDocuments);
  // Successful uploads arrive as real `documents`; only surface pending/failed here.
  const pending = items.filter((i) => i.status !== "done");

  const docIds = documents.map((d) => d.id).filter((id): id is string => Boolean(id));
  const checkedInView = docIds.filter((id) => checkedIds.has(id));

  // Drop ids that no longer exist (a doc was deleted, or the agent replaced the
  // set) so the selection count and "select all" state stay accurate.
  useEffect(() => {
    setCheckedIds((prev) => {
      const next = new Set([...prev].filter((id) => docIds.includes(id)));
      return next.size === prev.size ? prev : next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents]);

  useEffect(() => {
    if (checkedInView.length === 0 && bulkConfirm) setBulkConfirm(false);
  }, [checkedInView.length, bulkConfirm]);

  function toggleChecked(id: string) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function clearChecked() {
    setCheckedIds(new Set());
    setBulkConfirm(false);
  }

  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label="Expand sources"
          className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          <Icon name="panel-left-open" />
        </button>
        <span
          className="text-xs font-medium text-[var(--text-muted)]"
          style={{ writingMode: "vertical-rl" }}
        >
          Sources ({documents.length})
        </span>
      </div>
    );
  }

  return (
    <div
      className="relative flex h-full min-h-[320px] flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)]"
      onDragOver={(e) => {
        if (canAdd && e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setDragging(true);
        }
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={(e) => {
        if (!canAdd) return;
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length) upload(e.dataTransfer.files);
      }}
    >
      {dragging ? (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-[var(--mode-accent)] bg-[var(--bg)]/85 text-sm font-medium text-[var(--text)]">
          Drop to add a source
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2.5">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          Sources{documents.length ? ` · ${documents.length}` : ""}
        </h2>
        {onToggleCollapse ? (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label="Collapse sources"
            className="rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            <Icon name="panel-left-close" />
          </button>
        ) : null}
      </div>

      <div className="px-3 py-2">
        <input
          ref={inputRef}
          type="file"
          accept={UPLOAD_ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) upload(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={!canAdd}
          title={
            canAdd
              ? "Add a PDF, text, or Markdown file"
              : "Send a message first to start the session, then add sources"
          }
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-[var(--border)] px-3 py-2 text-sm text-[var(--text-muted)] hover:border-[var(--mode-accent)] hover:text-[var(--text)] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
        >
          <Icon name="plus" size={14} /> Add source
        </button>
      </div>

      {canMultiSelect && checkedInView.length > 0 ? (
        <div className="flex items-center gap-2 border-y border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-xs">
          {bulkConfirm ? (
            <>
              <span className="text-[var(--text)]">
                Delete {checkedInView.length} source{checkedInView.length > 1 ? "s" : ""}?
              </span>
              <span className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => {
                    onDeleteDocuments?.(checkedInView);
                    clearChecked();
                  }}
                  className="rounded px-2 py-0.5 font-medium text-red-300 hover:bg-red-500/15"
                >
                  Delete
                </button>
                <button
                  type="button"
                  onClick={() => setBulkConfirm(false)}
                  className="rounded px-2 py-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                >
                  Cancel
                </button>
              </span>
            </>
          ) : (
            <>
              <span className="font-medium text-[var(--text)]">
                {checkedInView.length} selected
              </span>
              <span className="ml-auto flex items-center gap-1.5">
                {checkedInView.length < docIds.length ? (
                  <button
                    type="button"
                    onClick={() => setCheckedIds(new Set(docIds))}
                    className="rounded px-1.5 py-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                  >
                    Select all
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={clearChecked}
                  className="rounded px-1.5 py-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() => setBulkConfirm(true)}
                  className="rounded px-2 py-0.5 font-medium text-red-300 hover:bg-red-500/15"
                >
                  Delete
                </button>
              </span>
            </>
          )}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto px-3 pb-3">
        {loading ? (
          <p className="px-1 py-2 text-xs text-[var(--text-muted)]">Loading…</p>
        ) : documents.length === 0 && pending.length === 0 ? (
          <p className="px-1 py-6 text-center text-xs text-[var(--text-muted)]">
            No sources yet. Add a PDF or text file and it becomes citable in the conversation.
          </p>
        ) : null}

        {pending.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-2 text-xs"
          >
            <Icon
              name={item.status === "uploading" ? "spinner" : "alert"}
              size={13}
              className={
                item.status === "error" ? "text-red-300" : "text-[var(--text-muted)]"
              }
            />
            <span className="min-w-0 flex-1 truncate">
              <span className="font-medium text-[var(--text)]">{item.name}</span>
              {item.error ? <span className="text-red-300"> — {item.error}</span> : null}
            </span>
            {item.status === "error" ? (
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label={`Dismiss ${item.name}`}
                className="shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
              >
                <Icon name="close" size={12} />
              </button>
            ) : null}
          </div>
        ))}

        {documents.map((doc) => {
          const label = doc.title || doc.source_url || "Untitled source";
          const canDelete = Boolean(onDeleteDocument && doc.id);
          const selectable = canMultiSelect && Boolean(doc.id);
          const isChecked = selectable && checkedIds.has(doc.id as string);
          const confirming = canDelete && confirmingId === doc.id;
          return (
            <div key={doc.id} className="group relative">
              {selectable ? (
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleChecked(doc.id as string)}
                  aria-label={`Select ${label}`}
                  className={`absolute left-2 top-2.5 z-10 h-3.5 w-3.5 cursor-pointer accent-[var(--mode-accent)] ${
                    isChecked || checkedInView.length > 0
                      ? "opacity-100"
                      : "opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  }`}
                />
              ) : null}
              <button
                type="button"
                onClick={() => setSelected(doc)}
                className={`block w-full rounded-lg border py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)] ${
                  isChecked
                    ? "border-[var(--mode-accent)] bg-[var(--surface-raised)]"
                    : "border-[var(--border)] bg-[var(--surface-raised)] hover:border-[var(--mode-accent)]"
                } ${selectable ? "pl-8" : "pl-2.5"} ${canDelete ? "pr-9" : "pr-2.5"}`}
              >
                <span className="block truncate text-sm font-medium text-[var(--text)]">
                  {label}
                </span>
                <span className="mt-0.5 block truncate text-xs text-[var(--text-muted)]">
                  {isWebSource(doc) ? hostOf(doc.source_url) : "file"}
                  {doc.content ? ` · ~${wordCount(doc.content).toLocaleString()} words` : ""}
                </span>
              </button>

              {canDelete && doc.id ? (
                confirming ? (
                  <span className="absolute right-1 top-1 flex items-center gap-1 rounded-md bg-[var(--surface)] px-1 py-0.5 shadow">
                    <button
                      type="button"
                      onClick={() => {
                        onDeleteDocument?.(doc.id as string);
                        setConfirmingId(null);
                      }}
                      className="rounded px-1.5 py-0.5 text-xs font-medium text-red-300 hover:bg-red-500/15"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmingId(null)}
                      className="rounded px-1.5 py-0.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmingId(doc.id as string)}
                    aria-label={`Delete ${label}`}
                    title={`Delete ${label}`}
                    className="absolute right-1 top-1 rounded p-1 text-[var(--text-muted)] opacity-0 hover:bg-[var(--surface)] hover:text-red-300 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Icon name="trash" size={14} />
                  </button>
                )
              ) : null}
            </div>
          );
        })}
      </div>

      {selected ? (
        <SourceViewer
          doc={selected}
          onClose={() => setSelected(null)}
          onDelete={
            onDeleteDocument && selected.id
              ? () => {
                  onDeleteDocument(selected.id as string);
                  setSelected(null);
                }
              : undefined
          }
        />
      ) : null}
    </div>
  );
}

function SourceViewer({
  doc,
  onClose,
  onDelete,
}: {
  doc: ResearchDocument;
  onClose: () => void;
  onDelete?: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={doc.title || "Source"}
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <h3 className="truncate text-sm font-semibold text-[var(--text)]">
            {doc.title || doc.source_url || "Source"}
          </h3>
          <div className="flex shrink-0 items-center gap-1">
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                className="rounded px-2 py-1 text-xs font-medium text-red-300 hover:bg-red-500/15"
              >
                Delete
              </button>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)]"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        </div>
        {isWebSource(doc) ? (
          <a
            href={doc.source_url}
            target="_blank"
            rel="noreferrer"
            className="truncate border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--mode-accent)] hover:underline"
          >
            {doc.source_url}
          </a>
        ) : null}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <pre className="whitespace-pre-wrap break-words font-sans text-sm text-[var(--text)]">
            {doc.content || "No extracted text."}
          </pre>
        </div>
      </div>
    </div>
  );
}
