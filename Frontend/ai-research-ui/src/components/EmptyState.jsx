/**
 * EmptyState – shown before any query is made.
 * Features animated background orbs and suggestion chips.
 */
export default function EmptyState({ onSuggestionClick }) {
  const suggestions = [
    "Explain transformer attention mechanisms",
    "Compare GPT-4 vs Claude on reasoning",
    "Latest advances in protein folding AI",
    "How does RLHF work?",
  ];

  return (
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      {/* Animated orbs */}
      <div className="relative mb-10 h-32 w-32">
        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-accent-500/15 to-cyan-500/10 blur-2xl animate-float" />
        <div
          className="absolute inset-4 rounded-full bg-gradient-to-tl from-accent-400/20 to-purple-500/10 blur-xl animate-float"
          style={{ animationDelay: "-2s" }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <svg
            className="h-14 w-14 text-accent-400/70"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2a4 4 0 014 4c0 1.95-2 4-4 6-2-2-4-4.05-4-6a4 4 0 014-4z" />
            <path d="M12 14c2 2 4 4.05 4 6a4 4 0 01-8 0c0-1.95 2-4 4-6z" />
            <path d="M2 12a4 4 0 014-4c1.95 0 4 2 6 4-2 2-4.05 4-6 4a4 4 0 01-4-4z" />
            <path d="M14 12c2-2 4.05-4 6-4a4 4 0 010 8c-1.95 0-4-2-6-4z" />
          </svg>
        </div>
      </div>

      <h2 className="mb-2 text-xl font-bold text-white tracking-tight">
        What would you like to explore?
      </h2>
      <p className="mb-8 max-w-sm text-center text-sm text-surface-400/80 leading-relaxed">
        Ask any research question and NeuronAI will synthesise insights from
        across the literature.
      </p>

      {/* Suggestion chips */}
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSuggestionClick?.(s)}
            className="rounded-full border border-surface-300/40 bg-surface-200/50 px-4 py-2 text-[13px] text-surface-400 backdrop-blur-sm transition-all duration-200 hover:border-accent-500/30 hover:text-accent-300 hover:bg-surface-200/80 hover:shadow-lg hover:shadow-accent-500/5 active:scale-95"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
