import { useState, useEffect } from "react";

/**
 * Header – top navigation bar with branding & status indicator.
 */
export default function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-surface-100/80 backdrop-blur-xl border-b border-surface-300/50 shadow-lg shadow-black/20"
          : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-accent-500 to-cyan-500 shadow-lg shadow-accent-500/25">
            <svg
              className="h-5 w-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-accent-400/20 to-cyan-400/20 animate-pulse-slow" />
          </div>

          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">
              Neuron<span className="text-accent-400">AI</span>
            </h1>
            <p className="text-[11px] leading-none font-medium text-surface-400 tracking-wide uppercase">
              Research Assistant
            </p>
          </div>
        </div>

        {/* Status pill */}
        <div className="flex items-center gap-2 rounded-full border border-surface-300/50 bg-surface-200/60 px-3.5 py-1.5 text-xs font-medium text-emerald-400 backdrop-blur-sm">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          Model Online
        </div>
      </div>
    </header>
  );
}
