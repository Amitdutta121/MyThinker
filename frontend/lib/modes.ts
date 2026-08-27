import type { ThinkingMode } from "./types";

export interface ModeStyle {
  label: string;
  description: string;
  accent: string;
  accentSoft: string;
}

/*
 * A deliberately narrow palette, not a spectrum. The five exploratory modes
 * share one cool analogous band (blue → indigo → teal, all desaturated) so the
 * per-turn `--mode-accent` tint shifts without lurching through a rainbow.
 * Only the two modes that carry a real signal break out: `challenge` warms to
 * amber (tension), `decide` goes green (commit).
 */
export const MODE_STYLES: Record<ThinkingMode, ModeStyle> = {
  capture: {
    label: "Capture",
    description: "Getting the idea down",
    accent: "#8ba3cf",
    accentSoft: "rgba(139, 163, 207, 0.16)",
  },
  clarify: {
    label: "Clarify",
    description: "Sharpening the frame",
    accent: "#6b9dd0",
    accentSoft: "rgba(107, 157, 208, 0.16)",
  },
  challenge: {
    label: "Challenge",
    description: "Testing assumptions",
    accent: "#d9945a",
    accentSoft: "rgba(217, 148, 90, 0.16)",
  },
  explore: {
    label: "Explore",
    description: "Generating alternatives",
    accent: "#9d94ce",
    accentSoft: "rgba(157, 148, 206, 0.16)",
  },
  research: {
    label: "Research",
    description: "Gathering evidence",
    accent: "#5fa5ad",
    accentSoft: "rgba(95, 165, 173, 0.16)",
  },
  converge: {
    label: "Converge",
    description: "Weighing tradeoffs",
    accent: "#8499cc",
    accentSoft: "rgba(132, 153, 204, 0.16)",
  },
  decide: {
    label: "Decide",
    description: "Committing to a path",
    accent: "#6cc191",
    accentSoft: "rgba(108, 193, 145, 0.16)",
  },
};

export function modeStyle(mode: ThinkingMode): ModeStyle {
  return MODE_STYLES[mode];
}
