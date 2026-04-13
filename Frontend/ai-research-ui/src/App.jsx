import { useCallback, useState, useEffect } from "react";
import Header from "./components/Header";
import SearchInput from "./components/SearchInput";
import EmptyState from "./components/EmptyState";
import LoadingSkeleton from "./components/LoadingSkeleton";
import ResultsList from "./components/ResultsList";
import ErrorBanner from "./components/ErrorBanner";
import QAChat from "./components/QAChat";
import { useResearch } from "./hooks/useResearch";

/**
 * App – root layout. Orchestrates state between components.
 */
export default function App() {
  const { query, results, isLoading, hasSearched, error, fetchResearch } = useResearch();
  
  // Try to find the first valid PDF path from the results to power the Q&A chat
  const [activePdfPath, setActivePdfPath] = useState(null);

  useEffect(() => {
    if (results && results.length > 0) {
      const firstWithPdf = results.find((r) => r.pdfPath);
      setActivePdfPath(firstWithPdf ? firstWithPdf.pdfPath : null);
    } else {
      setActivePdfPath(null);
    }
  }, [results]);

  const handleSuggestion = useCallback(
    (s) => {
      fetchResearch(s);
    },
    [fetchResearch]
  );

  return (
    <div className="relative min-h-screen overflow-hidden bg-surface-50">
      {/* Ambient background glow */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -top-32 left-1/2 h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-accent-500/[0.04] blur-[120px]" />
        <div className="absolute bottom-0 right-0 h-[400px] w-[500px] rounded-full bg-cyan-500/[0.03] blur-[100px]" />
      </div>

      <Header />

      {/* Main content */}
      <main className="relative z-10 mx-auto flex w-full max-w-7xl flex-col items-center px-6 pt-32 pb-20">
        {/* Hero area — only shown before first search */}
        {!hasSearched && (
          <div className="mb-8 text-center animate-fade-in">
            <h2 className="mb-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              AI-Powered{" "}
              <span className="bg-gradient-to-r from-accent-400 to-cyan-400 bg-clip-text text-transparent">
                Research
              </span>
            </h2>
            <p className="max-w-md mx-auto text-base text-surface-400/80 leading-relaxed">
              Instantly explore, synthesise, and understand the latest in
              artificial intelligence research.
            </p>
          </div>
        )}

        {/* Search bar — always visible */}
        <div className="w-full mb-10 max-w-2xl mx-auto">
          <SearchInput onSubmit={fetchResearch} isLoading={isLoading} />
        </div>

        {/* Dynamic content area */}
        <div className="w-full transition-all">
          {!hasSearched && (
            <div className="max-w-2xl mx-auto">
              <EmptyState onSuggestionClick={handleSuggestion} />
            </div>
          )}
          {error && (
            <div className="w-full mb-6 max-w-2xl mx-auto">
              <ErrorBanner message={error} onRetry={() => fetchResearch(query)} />
            </div>
          )}
          {isLoading && (
            <div className="max-w-2xl mx-auto">
              <LoadingSkeleton />
            </div>
          )}
          {!isLoading && !error && results.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start w-full">
              {/* Left Column: Research Results */}
              <div className={`col-span-1 border border-surface-300/30 rounded-xl bg-surface-100/50 backdrop-blur-sm p-6 shadow-xl ${activePdfPath ? 'lg:col-span-8' : 'lg:col-span-12'}`}>
                <ResultsList results={results} query={query} />
              </div>

              {/* Right Column: Q&A Chat widget */}
              {activePdfPath && (
                <div className="col-span-1 lg:col-span-4 sticky top-24">
                  <QAChat pdfPath={activePdfPath} />
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-surface-300/30 py-6 text-center text-xs text-surface-400/50">
        <p>
          NeuronAI Research Assistant · UI Prototype ·{" "}
          <span className="text-emerald-400/60">Live API connected</span>
        </p>
      </footer>
    </div>
  );
}
