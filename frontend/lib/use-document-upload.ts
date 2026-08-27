"use client";

import { useCallback, useState } from "react";
import type { ResearchDocument } from "./types";

/** Accept filter shared by every upload entry point; mirrors `ingest.SUPPORTED_SUFFIXES`. */
export const UPLOAD_ACCEPT = ".pdf,.txt,.md,.markdown,.text";
const UPLOAD_ACCEPT_RE = /\.(pdf|txt|md|markdown|text)$/i;

export interface UploadItem {
  id: string;
  name: string;
  status: "uploading" | "done" | "error";
  error?: string;
}

/**
 * Transient per-file upload state, shared by the Sources panel and the composer
 * drop target so both report progress the same way. Successful uploads surface
 * as real `ResearchDocument`s via the caller's own state; this hook only tracks
 * the in-flight and failed ones.
 */
export function useDocumentUpload(
  onUploadFile?: (file: File) => Promise<ResearchDocument>,
) {
  const [items, setItems] = useState<UploadItem[]>([]);

  const upload = useCallback(
    (files: Iterable<File>) => {
      if (!onUploadFile) return;
      for (const file of Array.from(files)) {
        const id = `${file.name}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
        if (!UPLOAD_ACCEPT_RE.test(file.name)) {
          setItems((prev) => [
            ...prev,
            { id, name: file.name, status: "error", error: "PDF, text, or Markdown only." },
          ]);
          continue;
        }
        setItems((prev) => [...prev, { id, name: file.name, status: "uploading" }]);
        onUploadFile(file)
          .then(() =>
            setItems((prev) =>
              prev.map((x) => (x.id === id ? { ...x, status: "done" as const } : x)),
            ),
          )
          .catch((err: unknown) =>
            setItems((prev) =>
              prev.map((x) =>
                x.id === id
                  ? {
                      ...x,
                      status: "error" as const,
                      error: err instanceof Error ? err.message : "Upload failed.",
                    }
                  : x,
              ),
            ),
          );
      }
    },
    [onUploadFile],
  );

  const dismiss = useCallback(
    (id: string) => setItems((prev) => prev.filter((x) => x.id !== id)),
    [],
  );

  const clearSettled = useCallback(
    () => setItems((prev) => prev.filter((x) => x.status === "uploading")),
    [],
  );

  return { items, upload, dismiss, clearSettled };
}
