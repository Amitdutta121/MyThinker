/**
 * The stream's `node` field on a "node" event is the *tool name* the agent just
 * ran (`ToolMessage.name` in `runtime._stream_agent`). Those are code
 * identifiers — `web_search`, `converge_ideas` — not something to show a user.
 * This maps the known tools to plain-language phrases and humanizes anything
 * unrecognized so a new tool still reads acceptably.
 */
const STEP_LABELS: Record<string, string> = {
  // research
  web_search: "Searching the web",
  fetch_url: "Reading a page",
  ingest_pdf: "Reading a PDF",
  list_indexed_documents: "Listing documents",
  search_documents: "Searching documents",
  // read-only board lookups
  get_project_snapshot: "Reviewing the board",
  get_evidence_ledger: "Checking the evidence",
  get_open_research_tasks: "Checking research tasks",
  get_branch_alternatives: "Reviewing alternatives",
  get_next_actions_plan: "Reviewing the plan",
  // state changes
  set_north_star: "Setting the north star",
  explore_ideas: "Exploring ideas",
  converge_ideas: "Weighing tradeoffs",
  commit_proposed_direction: "Committing the direction",
  record_user_decision: "Recording the decision",
  create_or_revise_plan: "Updating the plan",
  park_branch: "Parking a branch",
  save_evidence: "Saving evidence",
};

export function stepLabel(node: string): string {
  const known = STEP_LABELS[node];
  if (known) return known;
  const spaced = node.replace(/[_-]+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : node;
}
