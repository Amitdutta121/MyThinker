"use client";

/**
 * Route-level catch-all (Next.js App Router). The in-tree `ErrorBoundary`
 * around the chat and the rail handles the common case; this is the backstop
 * for anything that throws outside them so the user still gets a way back
 * instead of a blank page.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-lg font-semibold">Something broke.</h1>
      <p className="text-sm text-[var(--text-muted)]">{error.message}</p>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-[var(--mode-accent)] px-4 py-2 text-sm font-medium text-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
      >
        Try again
      </button>
    </div>
  );
}
