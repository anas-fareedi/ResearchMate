/**
 * Format search results returned from the backend into a standardized frontend format.
 *
 * @param {Array|Object} data - The raw data returned by the backend API.
 * @returns {Array} - The formatted results array for the UI.
 */
export const formatResearchResults = (data) => {
  if (!data) return [];

  const rawArray = Array.isArray(data) ? data : [data];

  return rawArray.map((item, idx) => ({
    title: item.title || `Research Result ${idx + 1}`,
    summary: item.summary || item.text || "No summary provided by the API.",
    tags: item.tags || ["AI", "Research"],
    confidence: item.confidence || 95,
    pdfPath: item.pdf_path || null,
    source: item.pdf_path
      ? `http://127.0.0.1:8000/download-pdf?path=${encodeURIComponent(
          item.pdf_path
        )}`
      : item.source || "Unknown source",
  }));
};
