"use client";
import { useState } from "react";
import { useCitizen } from "@/lib/useCitizen";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function ExplorePage() {
  const { citizenId, loading: authLoading } = useCitizen();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!citizenId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/citizen/${citizenId}/explore?scheme_name_query=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error("Request failed");
      setResult(await res.json());
    } catch {
      setError("The backend isn't reachable right now.");
    } finally {
      setLoading(false);
    }
  }

  if (authLoading || !citizenId) return <main className="p-8">Loading…</main>;

  return (
    <main className="p-8 max-w-xl">
      <h1 className="text-2xl font-bold mb-6">Why Wasn't I Matched?</h1>
      <div className="flex gap-2">
        <input
          className="border rounded px-3 py-2 flex-1"
          placeholder="Search a scheme, e.g. 'farmer scheme' or 'pension'…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <button className="bg-slate-800 text-white px-4 py-2 rounded" onClick={search}>
          Search
        </button>
      </div>

      {loading && <p className="mt-4">Searching…</p>}
      {error && <p className="mt-4 text-rose-600">{error}</p>}

      {result && !result.scheme && (
        <div className="mt-6 border rounded-lg p-4 bg-amber-50 border-amber-200">
          <p className="text-sm">{result.no_match_message}</p>
        </div>
      )}

      {result && result.scheme && (
        <div className="mt-6 border rounded-lg p-4">
          <h2 className="font-semibold">{result.scheme}</h2>
          {result.matched ? (
            <p className="text-emerald-700 mt-2">You currently match this scheme.</p>
          ) : (
            <>
              <p className="mt-2">
                <span className="font-medium">Blocking criterion:</span>{" "}
                {result.disqualifying_criterion}
              </p>
              <p className="mt-1">
                <span className="font-medium">Fixable?</span>{" "}
                {result.fixable ? "Yes — this can change" : "No — this is a fixed cutoff"}
              </p>
              <p className="text-sm text-slate-600 mt-2">{result.explanation}</p>
            </>
          )}
        </div>
      )}
    </main>
  );
}