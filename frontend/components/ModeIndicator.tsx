"use client";

import { motion } from "motion/react";
import { modeStyle } from "@/lib/modes";
import type { ThinkingMode } from "@/lib/types";

export default function ModeIndicator({ mode }: { mode: ThinkingMode }) {
  const style = modeStyle(mode);

  // Keyed remount on `mode` change plays the enter animation; no exit animation,
  // so a rapid sequence of mode changes (as tools run mid-turn) can't leave an
  // orphaned exiting node stuck on screen.
  return (
    <motion.div
      key={mode}
      data-testid="mode-indicator"
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm"
      style={{
        borderColor: style.accent,
        backgroundColor: style.accentSoft,
        color: style.accent,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: style.accent }} />
      <span className="font-medium">{style.label}</span>
      <span className="text-xs opacity-70">{style.description}</span>
    </motion.div>
  );
}
