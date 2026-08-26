# Session Handoff

## Completed

- Milestone slice `M7c` completed: the Next.js immersive workspace — the
  final slice of `M7: Immersive UI layer` (M7a HTTP API, M7b SSE streaming,
  M7c this frontend). `M7` is now fully done.
- New top-level `frontend/` directory: Next.js 15 (App Router) + TypeScript +
  Tailwind v4 + Framer Motion (`motion` package), talking to the existing API
  over HTTP only — no Python imports, no duplicated business logic.
  - `lib/api-types.ts`: generated via `openapi-typescript` from the live
    `GET /openapi.json` (`npm run generate:types`, requires the backend
    running). This is the mechanism that keeps frontend types from drifting
    out of sync with `src/mythinking/state.py`, the schema authority, instead
    of hand-duplicating the Pydantic models.
  - `lib/types.ts`: re-exports the generated schema types, plus one
    hand-written exception — `TurnStreamEvent`/`TurnStreamEventType` — because
    `POST /turns/stream` returns a plain `StreamingResponse` with no declared
    `response_model`, so FastAPI's OpenAPI schema can't describe its body
    (see the `unknown` content type on that operation in `api-types.ts`). Kept
    in sync by hand with `TurnStreamEvent` in `state.py`; a comment in
    `types.ts` notes this.
  - `lib/sse.ts`: hand-rolled `text/event-stream` parser over
    `fetch`'s `ReadableStream<Uint8Array>` (`parseEventStream`), since
    `POST /turns/stream` requires a POST body and browser `EventSource` only
    supports GET. Handles frames split across chunk boundaries and a trailing
    frame with no closing blank line.
  - `lib/api-client.ts`: `listProjects`, `getProject` (404 → `null`),
    `createTurn`, `streamTurn` (async generator over `parseEventStream`).
    `ApiError` carries the HTTP status and the API's `detail` string.
  - `components/Workspace.tsx`: owns all client state for one project —
    chat history (not persisted server-side; there's no transcript in
    `ProjectState`, only structured artifacts, so a resumed session starts
    with an empty chat panel showing the *existing* workspace state), live
    streaming step chips, the live/settled `current_mode`, and the session
    list. Drives `ChatPanel`, `ModeIndicator`, `SessionSelector`, and the five
    workspace panels.
  - `components/ChatPanel.tsx`: composer (Enter to send, Shift+Enter for a
    newline) + message history + transient `NODE`-event step chips (animated
    in/out) + inline retryable error banner.
  - `components/ModeIndicator.tsx`: `AnimatePresence`-driven badge, colored
    per `ThinkingMode` via `lib/modes.ts`; updates live off streaming `NODE`
    events' `mode` field while a turn is in flight, then settles to the
    refreshed `ProjectState.current_mode`.
  - `components/SessionSelector.tsx`: `GET /projects` list + new-session
    action.
  - `components/workspace-panels/{NorthStarCard,BranchGraph,EvidenceTimeline,
    DecisionHistory,NextActionsPanel}.tsx`: pure presentational, each fed by
    one `ProjectState`. `BranchGraph` groups branches into status lanes
    (active/parked/merged/discarded) rather than a full graph-layout library.
    `NextActionsPanel` is read-only — there's no PATCH endpoint for
    `NextAction.completed`, and adding one would be new backend business
    logic outside this slice's scope.
  - `app/page.tsx` (new session) and `app/session/[projectId]/page.tsx`
    (resume) both render `Workspace`, differing only in `initialProjectId`.
- Backend (minimal, both explicitly deferred from M7a/M7b to this slice):
  - `src/mythinking/api.py`: added `CORSMiddleware`, allowing
    `http://localhost:3000`, `:3001` and both `127.0.0.1` equivalents (the
    `:3001` fallback was added after the manual smoke test found a stray,
    unrelated `node.exe` process already holding port 3000 on this machine —
    Next.js silently falls back to 3001 in that case, so both are allowed
    rather than assuming 3000 is free). No new `Settings` field — see
    Decisions locked.
  - `tests/test_api.py`: two new CORS tests (`:3000` and `:3001`).
- Frontend tests (Vitest + React Testing Library + jsdom, all offline —
  fixtures in `frontend/tests/fixtures/`, no live backend or LLM needed):
  `sse.test.ts` (frame parsing incl. chunk-boundary splits), `api-client.test.ts`
  (mocked `fetch`), `SessionSelector.test.tsx`, `ChatPanel.test.tsx`, and one
  test file per workspace panel. 24 tests, all passing.
- Docs: `README.md` (Frontend section, CORS note, foundation layout,
  "current runnable flow" now says M7 is complete), `.gitignore`
  (`frontend/node_modules/`, `.next/`, `out/`, `.env.local`).
- Commands run:
  - Backend: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest`
    (156 passed, up from 154)
  - Frontend (`cd frontend`): `npm install`, `npx tsc --noEmit` (clean),
    `npx vitest run` (24/24 passed), `npx next build` (clean production
    build, no dependency on a live backend)
  - Manual smoke test: ran `uv run mythinking serve --port 8000` and
    `npm run dev` (landed on `:3001`, see above) together, drove the app
    through `claude-in-chrome` against the real configured OpenRouter model —
    submitted a message on a brand-new session, watched the `NODE` step chips
    and the `ModeIndicator` animate live (`capture` → `clarify`), confirmed
    the URL was promoted to `/session/<id>` without losing the just-streamed
    turn, confirmed North Star / Evidence panels populated from the real
    model output, opened `SessionSelector` (showed all 3 persisted projects
    with mode + relative time), switched sessions and confirmed the workspace
    panels reloaded correctly, reloaded a `/session/[id]` URL directly with a
    clean console. No console errors at any point.

## Decisions locked

- CORS origins are hardcoded in `create_app` (not a new `Settings` field) —
  this is a local, no-auth, personal tool; a small dev-origin allow-list
  matches the existing scope discipline in `AGENTS.md` rather than adding
  config surface for a single-user local app.
- `Workspace.tsx` promotes a brand-new session's URL to `/session/[id]` using
  `window.history.replaceState`, **not** `router.replace`. This was found and
  fixed during the manual smoke test: `/` and `/session/[projectId]` are
  different route components, so a Next.js router navigation between them
  unmounts and remounts `Workspace`, silently discarding the chat
  history/mode state the turn that just streamed had just produced. Plain
  History API avoids the remount while still updating the address bar for
  reload/share. `router.push`/`router.replace` are still used (deliberately)
  for `SessionSelector`'s session-switch and new-session actions, where a
  full reset of local chat state is the intended behavior.
- Chat message history lives only in `Workspace`'s client state, not in
  `ProjectState`. There is no conversation transcript field anywhere in the
  backend (`state.py`'s `ProjectState` only holds structured artifacts), so
  resuming a session via the selector intentionally shows an empty chat panel
  with the accumulated workspace state (north star, branches, evidence,
  decisions, next actions) — nothing was fabricated to paper over this gap.
- `lib/api-types.ts` is generated and committed rather than generated at
  build time, so `npm run build`/`test`/`typecheck` never require a live
  backend. Regenerate with `npm run generate:types` after any change to
  `state.py`'s API-exposed models.
- Tailwind v4's CSS-first config (`@import "tailwindcss"` in
  `app/globals.css` + `@tailwindcss/postcss`) is used instead of a
  `tailwind.config.ts` — no theme customization was needed beyond the CSS
  custom properties already defined in `globals.css` for the mode-accent
  system.

## Open issues

- `npm audit` reports 7 advisories (1 critical, 2 high, 4 moderate), all in
  dev-only transitive dependencies (`esbuild`'s dev-server request-forwarding
  issue via `vite`/`vitest`, and `postcss`'s source-map/XSS issues via
  `next`'s bundled build tooling). None are reachable in the shipped
  production bundle for this local, single-user tool. Fixing requires major
  version bumps (`vitest` 2→4, `next` 15→16) that are out of scope for this
  slice; left as-is deliberately rather than force-upgrading unrelated to the
  milestone.
- Observed, out-of-scope model-behavior quirk during the smoke test: on one
  turn, the Frame Analyst's `message` field ended with the same question also
  populated separately in `question`, so `ChatPanel` (which renders both
  fields, per the API contract) showed the question text twice. This is a
  prompt/specialist-output concern (`prompts/`), not a frontend bug — noted
  here for whoever next touches the Frame Analyst prompt or evals, not acted
  on in this slice.
- No CORS configuration for anything beyond local dev ports — unchanged
  scope from M7a/M7b's "local-first, no-auth" framing; a real deployment
  story was never in scope for M7.
- `M6c` (optional user profile extraction) is still not started — it was
  explicitly deprioritized behind `M7` in the M7a/M7b handoffs, and M7 is now
  fully done.

## Next best task

- `M6c`: optional user profile extraction, off by default — the last
  unstarted item in the milestone plan (`docs/IMPLEMENTATION_PLAN.md`).
- Alternatively, if the user wants to keep building on the M7c UI rather than
  start a new milestone: the next natural UI slice would be surfacing
  `research_tasks`/`open_questions`/`parked_ideas` (currently in
  `ProjectState` but not rendered anywhere in the workspace panels), or
  adding a `NextAction.completed` PATCH endpoint plus a toggle in
  `NextActionsPanel` — both deliberately left out of this slice as scope, not
  forgotten.
