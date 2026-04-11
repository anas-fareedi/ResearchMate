/**
 * ResultCard – displays a single research result.
 *
 * Props:
 *   title: string
 *   summary: string
 *   tags: string[]
 *   confidence: number (0‑100)
 *   source: string
 *   index: number – controls staggered entrance
 */
export default function ResultCard({
  title = "Untitled",
  summary = "",
  tags = [],
  confidence = 0,
  source = "",
  index = 0,
}) {
  const confidenceColor =
    confidence >= 80
      ? "text-emerald-400"
      : confidence >= 50
      ? "text-amber-400"
      : "text-red-400";

  const confidenceBarColor =
    confidence >= 80
      ? "from-emerald-500 to-emerald-400"
      : confidence >= 50
      ? "from-amber-500 to-amber-400"
      : "from-red-500 to-red-400";

  return (
    <article
      className="glass-card group rounded-2xl p-6 transition-all duration-300 animate-slide-up hover:translate-y-[-2px] hover:shadow-xl hover:shadow-accent-500/5"
      style={{ animationDelay: `${index * 100}ms` }}
      id={`result-card-${index}`}
    >
      {/* Top row: icon + title + confidence */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent-500/20 to-cyan-500/10 text-accent-400 transition-colors duration-200 group-hover:from-accent-500/30 group-hover:to-cyan-500/20">
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>

          <h3 className="text-base font-semibold leading-snug text-white group-hover:text-accent-300 transition-colors duration-200">
            {title}
          </h3>
        </div>

        {/* Confidence badge */}
        <div className="flex flex-col items-end gap-1">
          <span
            className={`text-xs font-bold tabular-nums ${confidenceColor}`}
          >
            {confidence}%
          </span>
          <div className="h-1 w-12 overflow-hidden rounded-full bg-surface-300/40">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${confidenceBarColor} transition-all duration-700`}
              style={{ width: `${confidence}%` }}
            />
          </div>
        </div>
      </div>

      {/* Summary */}
      <p className="mb-4 text-sm leading-relaxed text-gray-400">
        {summary}
      </p>

      {/* Footer: tags + source */}
      <div className="flex flex-wrap items-center gap-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-surface-300/50 bg-surface-200/50 px-2.5 py-0.5 text-[11px] font-medium text-surface-400 transition-colors duration-200 hover:border-accent-500/30 hover:text-accent-400"
          >
            {tag}
          </span>
        ))}

        {source && (
  <a
    href={source}
    target="_blank"
    rel="noopener noreferrer"
    className="ml-auto text-[11px] text-blue-400 underline truncate max-w-[180px] hover:text-blue-300"
  >
    📎 Open PDF
  </a>
)}
      </div>
    </article>
  );
}
