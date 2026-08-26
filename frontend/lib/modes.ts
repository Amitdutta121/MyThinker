import type { ThinkingMode } from "./types";

export interface ModeStyle {
  label: string;
  description: string;
  accent: string;
  accentSoft: string;
}

export const MODE_STYLES: Record<ThinkingMode, ModeStyle> = {
  capture: {
    label: "Capture",
    description: "Getting the idea down",
    accent: "#7c9cff",
    accentSoft: "rgba(124, 156, 255, 0.16)",
  },
  clarify: {
    label: "Clarify",
    description: "Sharpening the frame",
    accent: "#63c7ff",
    accentSoft: "rgba(99, 199, 255, 0.16)",
  },
  challenge: {
    label: "Challenge",
    description: "Testing assumptions",
    accent: "#ff8a5c",
    accentSoft: "rgba(255, 138, 92, 0.16)",
  },
  explore: {
    label: "Explore",
    description: "Generating alternatives",
    accent: "#b98bff",
    accentSoft: "rgba(185, 139, 255, 0.16)",
  },
  research: {
    label: "Research",
    description: "Gathering evidence",
    accent: "#3fd0c9",
    accentSoft: "rgba(63, 208, 201, 0.16)",
  },
  converge: {
    label: "Converge",
    description: "Weighing tradeoffs",
    accent: "#f5c453",
    accentSoft: "rgba(245, 196, 83, 0.16)",
  },
  decide: {
    label: "Decide",
    description: "Committing to a path",
    accent: "#5cd68a",
    accentSoft: "rgba(92, 214, 138, 0.16)",
  },
};

export function modeStyle(mode: ThinkingMode): ModeStyle {
  return MODE_STYLES[mode];
}
