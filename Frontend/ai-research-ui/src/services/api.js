/**
 * API service – single module for all backend communication.
 *
 * Base URL defaults to localhost:8000 during development.
 * Override via VITE_API_URL env variable in production.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

/**
 * POST /research
 *
 * @param   {string}  query  – the user's research question
 * @returns {Promise<{ results: Array<{ title, summary, tags, confidence, source }> }>}
 * @throws  {Error}   on network / server errors
 */
export async function postResearch(query) {
  const res = await fetch(`${BASE_URL}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(
      `Research API returned ${res.status}${errorBody ? `: ${errorBody}` : ""}`
    );
  }

  return res.json();
}
