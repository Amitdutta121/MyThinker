"use client";

import { useEffect, useState } from "react";
import Icon from "../Icon";

/**
 * Click-to-edit text. Renders as plain text with a hover pencil until clicked,
 * then an input/textarea that saves on Enter or blur and cancels on Escape.
 * `onSave` is only called when the trimmed value actually changed and is
 * non-empty; the control is disabled while the save is in flight.
 */
export default function InlineEdit({
  value,
  onSave,
  ariaLabel,
  placeholder = "—",
  className = "",
  multiline = false,
}: {
  value: string;
  onSave: (next: string) => Promise<void> | void;
  ariaLabel: string;
  placeholder?: string;
  className?: string;
  multiline?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  const commit = async () => {
    const next = draft.trim();
    if (next === value.trim() || next === "") {
      setEditing(false);
      setDraft(value);
      return;
    }
    setBusy(true);
    try {
      await onSave(next);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        aria-label={ariaLabel}
        className={`group/inline inline-flex items-start gap-1 text-left ${className}`}
      >
        <span>
          {value || <span className="text-[var(--text-muted)]">{placeholder}</span>}
        </span>
        <Icon
          name="pencil"
          size={13}
          className="mt-0.5 shrink-0 text-[var(--text-muted)] opacity-0 transition-opacity group-hover/inline:opacity-100"
        />
      </button>
    );
  }

  const commonProps = {
    autoFocus: true,
    "aria-label": ariaLabel,
    disabled: busy,
    value: draft,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setDraft(event.target.value),
    onBlur: commit,
    onKeyDown: (event: React.KeyboardEvent) => {
      if (event.key === "Enter" && !multiline) {
        event.preventDefault();
        commit();
      }
      if (event.key === "Escape") {
        setEditing(false);
        setDraft(value);
      }
    },
    className: `w-full rounded border border-[var(--mode-accent)] bg-[var(--bg)] px-1.5 py-0.5 ${className}`,
  };

  return multiline ? (
    <textarea rows={3} {...commonProps} />
  ) : (
    <input type="text" {...commonProps} />
  );
}
