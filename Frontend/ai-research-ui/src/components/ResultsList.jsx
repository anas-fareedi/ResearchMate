import ResultCard from "./ResultCard";

/**
 * ResultsList – renders an array of results as cards.
 *
 * Props:
 *   results: Array<{ title, summary, tags, confidence, source }>
 *   query: string – the original user query (shown as heading)
 */
export default function ResultsList({ results = [], query = "" }) {
  if (!results.length) return null;

  return (
    <section className="w-full animate-fade-in">
      {/* Section header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-surface-400/60 mb-1">
            Results for
          </p>
          <h2 className="text-lg font-bold text-white leading-snug truncate max-w-md">
            &ldquo;{query}&rdquo;
          </h2>
        </div>
        <span className="rounded-full border border-surface-300/40 bg-surface-200/50 px-3 py-1 text-xs tabular-nums text-surface-400">
          {results.length} finding{results.length !== 1 && "s"}
        </span>
      </div>

      {/* Cards */}
      <div className="space-y-4">
        {results.map((r, i) => (
          <ResultCard key={i} {...r} index={i} />
        ))}
      </div>
    </section>
  );
}
