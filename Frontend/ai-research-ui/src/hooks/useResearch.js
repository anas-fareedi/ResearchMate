import { useState, useCallback } from "react";
import { postResearch } from "../services/api";
import { formatResearchResults } from "../utils/formatters";

/**
 * Custom hook to manage the state and logic for fetching research data.
 */
export const useResearch = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState(null);

  const fetchResearch = useCallback(async (searchQuery) => {
    setQuery(searchQuery);
    setResults([]);
    setError(null);
    setIsLoading(true);
    setHasSearched(true);

    try {
      const data = await postResearch(searchQuery);
      const formattedResults = formatResearchResults(data);
      setResults(formattedResults);
    } catch (err) {
      console.error("Research API Error:", err);
      setError(
        err.message ||
          "Failed to reach the research API. Ensure the backend is running."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    query,
    results,
    isLoading,
    hasSearched,
    error,
    fetchResearch,
  };
};
