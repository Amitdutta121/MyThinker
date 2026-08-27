/**
 * One small stroke-icon set for the whole UI. Replaces the mix of colour emoji
 * (📎 📄 🗑 ⚠️) and ad-hoc Unicode glyphs (✕ » « ▸ ▲ ▼ ›) the panels used to
 * reach for — those render differently per OS and clash with the muted palette.
 *
 * All icons inherit `currentColor`, sit on a 16-unit grid, and are marked
 * `aria-hidden` (the surrounding control carries the label).
 */

type IconName =
  | "paperclip"
  | "file"
  | "trash"
  | "alert"
  | "pencil"
  | "plus"
  | "close"
  | "chevron-right"
  | "chevron-down"
  | "chevron-up"
  | "panel-left-close"
  | "panel-left-open"
  | "arrow-down"
  | "spinner";

const PATHS: Record<IconName, React.ReactNode> = {
  paperclip: (
    <path d="M13 5.5 6.5 12a2.5 2.5 0 0 1-3.5-3.5l6.5-6.5a1.7 1.7 0 0 1 2.4 2.4L5.7 10.8a.9.9 0 0 1-1.3-1.3l5.6-5.6" />
  ),
  file: (
    <>
      <path d="M9 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5.5Z" />
      <path d="M9 1.5V5.5H13" />
    </>
  ),
  trash: (
    <>
      <path d="M2.5 4h11" />
      <path d="M6 4V2.5h4V4" />
      <path d="M3.5 4l.6 9a1 1 0 0 0 1 .9h5.8a1 1 0 0 0 1-.9l.6-9" />
      <path d="M6.5 7v4M9.5 7v4" />
    </>
  ),
  alert: (
    <>
      <path d="M8 2 1.5 13.5h13Z" />
      <path d="M8 6.5v3.5" />
      <path d="M8 12h.01" />
    </>
  ),
  pencil: (
    <>
      <path d="M11 2.5 13.5 5 5 13.5H2.5V11Z" />
      <path d="M9.5 4 12 6.5" />
    </>
  ),
  plus: <path d="M8 3v10M3 8h10" />,
  close: <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />,
  "chevron-right": <path d="M6 3.5 10.5 8 6 12.5" />,
  "chevron-down": <path d="M3.5 6 8 10.5 12.5 6" />,
  "chevron-up": <path d="M3.5 10 8 5.5 12.5 10" />,
  "panel-left-close": (
    <>
      <rect x="2" y="2.5" width="12" height="11" rx="1.5" />
      <path d="M6.5 2.5v11" />
      <path d="M11 6 9 8l2 2" />
    </>
  ),
  "panel-left-open": (
    <>
      <rect x="2" y="2.5" width="12" height="11" rx="1.5" />
      <path d="M6.5 2.5v11" />
      <path d="M9 6l2 2-2 2" />
    </>
  ),
  "arrow-down": (
    <>
      <path d="M8 2.5v11" />
      <path d="M3.5 9 8 13.5 12.5 9" />
    </>
  ),
  spinner: <path d="M8 1.5a6.5 6.5 0 1 1-6.5 6.5" />,
};

export default function Icon({
  name,
  size = 16,
  className = "",
  strokeWidth = 1.5,
}: {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`${name === "spinner" ? "animate-spin " : ""}${className}`}
    >
      {PATHS[name]}
    </svg>
  );
}
