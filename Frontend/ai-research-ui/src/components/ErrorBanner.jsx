/**
 * ErrorBanner – displays API / network errors with a retry action.
 *
 * Props:
 *   message: string
 *   onRetry: () => void
 */
export default function ErrorBanner({ message, onRetry }) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className="w-full animate-fade-in rounded-2xl border border-red-500/20 bg-red-500/[0.06] p-5 backdrop-blur-sm"
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-500/10 text-red-400">
          <svg
            className="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        <div className="flex-1">
          <h4 className="text-sm font-semibold text-red-300">
            Something went wrong
          </h4>
          <p className="mt-1 text-sm leading-relaxed text-red-400/80">
            {message}
          </p>
        </div>

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="shrink-0 rounded-lg border border-red-500/20 bg-red-500/10 px-3.5 py-1.5 text-xs font-semibold text-red-300 transition-all duration-200 hover:bg-red-500/20 hover:border-red-500/30 active:scale-95"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
