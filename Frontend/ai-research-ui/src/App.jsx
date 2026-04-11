import { useState, useCallback } from "react";
import Header from "./components/Header";
import SearchInput from "./components/SearchInput";
import EmptyState from "./components/EmptyState";
import LoadingSkeleton from "./components/LoadingSkeleton";
import ResultsList from "./components/ResultsList";
import ErrorBanner from "./components/ErrorBanner";
import { postResearch } from "./services/api";

/**
 * App – root layout. Orchestrates state between components.
 */
export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = useCallback(async (q) => {
    setQuery(q);
    setResults([]);
    setError(null);
    setIsLoading(true);
    setHasSearched(true);

    try {
      const data = await postResearch(q);

      // Convert backend response to frontend format map
      let formattedResult = [];
      if (Array.isArray(data)) {
         formattedResult = data.map((item, idx) => ({
            title: item.title || `Research Result ${idx + 1}`,
            summary: item.summary || item.text || "No summary provided by the API.",
            tags: item.tags || ["AI", "Research"],
            confidence: item.confidence || 95,
            source: item.pdf_path
  ? `http://127.0.0.1:8000/download-pdf?path=${encodeURIComponent(item.pdf_path)}`
  : item.source || "Unknown source",
         }));
      } else {
         formattedResult = [
          {
            title: data.title || "Research Summary",
            summary: data.summary || data.text || "No summary provided by the API.",
            tags: data.tags || ["AI", "Research"],
            confidence: data.confidence || 95,
            source: data.pdf_path
  ? `http://127.0.0.1:8000/download-pdf?path=${encodeURIComponent(data.pdf_path)}`
  : data.source || "Unknown source",
          }
        ];
      }

      setResults(formattedResult);
    } catch (err) {
      console.error("Error:", err);
      setError(err.message || "Failed to reach the research API. Ensure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSuggestion = useCallback(
    (s) => {
      handleSearch(s);
    },
    [handleSearch]
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
      <main className="relative z-10 mx-auto flex max-w-2xl flex-col items-center px-6 pt-32 pb-20">
        {/* Hero area — only shown before first search */}
        {!hasSearched && (
          <div className="mb-8 text-center animate-fade-in">
            <h2 className="mb-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              AI-Powered{" "}
              <span className="bg-gradient-to-r from-accent-400 to-cyan-400 bg-clip-text text-transparent">
                Research
              </span>
            </h2>
            <p className="max-w-md text-base text-surface-400/80 leading-relaxed">
              Instantly explore, synthesise, and understand the latest in
              artificial intelligence research.
            </p>
          </div>
        )}

        {/* Search bar — always visible */}
        <div className="w-full mb-10">
          <SearchInput onSubmit={handleSearch} isLoading={isLoading} />
        </div>

        {/* Dynamic content area */}
        {!hasSearched && <EmptyState onSuggestionClick={handleSuggestion} />}
        {error && (
          <div className="w-full mb-6">
            <ErrorBanner message={error} onRetry={() => handleSearch(query)} />
          </div>
        )}
        {isLoading && <LoadingSkeleton />}
        {!isLoading && !error && results.length > 0 && (
          <ResultsList results={results} query={query} />
        )}
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
