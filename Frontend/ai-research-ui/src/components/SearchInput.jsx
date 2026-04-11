import { useState } from "react";

/**
 * SearchInput – main query box with submit button.
 *
 * Props:
 *   onSubmit(query: string) – fires when the user submits.
 *   isLoading: boolean       – disables the button during a request.
 */
export default function SearchInput({ onSubmit, isLoading = false }) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full animate-fade-in">
      <div className="input-glow group relative flex items-center rounded-2xl border border-surface-300/60 bg-surface-200/70 transition-all duration-300 focus-within:border-accent-500/40">
        {/* Search Icon */}
        <div className="pointer-events-none pl-5 text-surface-400 transition-colors duration-200 group-focus-within:text-accent-400">
          <svg
            className="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        </div>

        {/* Text Input */}
        <input
          id="search-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a research question…"
          className="flex-1 bg-transparent py-4 px-4 text-[15px] text-white placeholder:text-surface-400/70 outline-none"
        />

        {/* Submit Button */}
        <button
          id="submit-btn"
          type="submit"
          disabled={!query.trim() || isLoading}
          className="mr-2 flex items-center gap-2 rounded-xl bg-gradient-to-r from-accent-500 to-accent-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-accent-500/20 transition-all duration-200 hover:shadow-accent-500/40 hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:hover:brightness-100 active:scale-95"
        >
          {isLoading ? (
            <>
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="3"
                  className="opacity-25"
                />
                <path
                  d="M4 12a8 8 0 018-8"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              </svg>
              Thinking…
            </>
          ) : (
            <>
              Explore
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14" />
                <path d="M12 5l7 7-7 7" />
              </svg>
            </>
          )}
        </button>
      </div>

      {/* Keyboard hint */}
      <p className="mt-3 text-center text-xs text-surface-400/60">
        Press{" "}
        <kbd className="rounded border border-surface-300/50 bg-surface-200/60 px-1.5 py-0.5 font-mono text-[10px] text-surface-400">
          Enter
        </kbd>{" "}
        to search · Powered by AI
      </p>
    </form>
  );
}
