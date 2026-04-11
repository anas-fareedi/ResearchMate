/**
 * LoadingSkeleton – animated skeleton cards shown while a result loads.
 */
export default function LoadingSkeleton() {
  return (
    <div className="w-full space-y-5 animate-fade-in" role="status" aria-label="Loading results">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="glass-card overflow-hidden rounded-2xl p-6"
          style={{ animationDelay: `${i * 120}ms` }}
        >
          {/* Title skeleton */}
          <div className="mb-4 flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-surface-300/50 animate-pulse" />
            <div className="h-4 w-48 rounded-full bg-surface-300/50 animate-pulse" />
          </div>

          {/* Body lines */}
          <div className="space-y-3">
            <div className="relative h-3 w-full overflow-hidden rounded-full bg-surface-300/30">
              <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-surface-300/30 to-transparent" />
            </div>
            <div className="relative h-3 w-5/6 overflow-hidden rounded-full bg-surface-300/30">
              <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-surface-300/30 to-transparent" style={{ animationDelay: "150ms" }} />
            </div>
            <div className="relative h-3 w-3/4 overflow-hidden rounded-full bg-surface-300/30">
              <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-surface-300/30 to-transparent" style={{ animationDelay: "300ms" }} />
            </div>
          </div>

          {/* Footer pills */}
          <div className="mt-5 flex gap-2">
            <div className="h-6 w-16 rounded-full bg-surface-300/30 animate-pulse" />
            <div className="h-6 w-20 rounded-full bg-surface-300/30 animate-pulse" style={{ animationDelay: "200ms" }} />
            <div className="h-6 w-14 rounded-full bg-surface-300/30 animate-pulse" style={{ animationDelay: "400ms" }} />
          </div>
        </div>
      ))}

      <p className="text-center text-sm text-surface-400/60 animate-pulse">
        Synthesising findings from multiple sources…
      </p>
    </div>
  );
}
