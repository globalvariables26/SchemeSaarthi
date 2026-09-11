"use client";
import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const DEMO_CITIZEN_ID = "76f2232e-9707-4a2a-8298-1f8facbb6200";

type MatchRow = {
  id: string;
  status: string;
  confidence: number;
  schemes?: { name: string; description: string };
};

const STATUS_COLORS: Record<string, string> = {
  matched: "bg-emerald-100 text-emerald-800 border-emerald-300",
  needs_document: "bg-amber-100 text-amber-800 border-amber-300",
  conflicting: "bg-rose-100 text-rose-800 border-rose-300",
  uncertain: "bg-slate-100 text-slate-700 border-slate-300",
  rejected: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function DashboardPage() {
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/citizen/${DEMO_CITIZEN_ID}/matches`)
      .then((res) => res.json())
      .then((data) => setMatches(data))
      .catch(() => setError("Couldn't load matches — is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Your Matched Schemes</h1>
      {loading && <p>Loading…</p>}
      {error && <p className="text-rose-600">{error}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        {matches.map((m) => (
          <div key={m.id} className="border rounded-lg p-4 shadow-sm">
            <h2 className="font-semibold">{m.schemes?.name || "Unknown scheme"}</h2>
            <p className="text-sm text-slate-600 mt-1">{m.schemes?.description}</p>
            <div className="mt-3 flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded-full border ${STATUS_COLORS[m.status] || ""}`}>
                {m.status.replace("_", " ")}
              </span>
              <span className="text-xs text-slate-500">
                Confidence: {Math.round((m.confidence || 0) * 100)}%
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Preliminary match only — not an official determination.
            </p>
          </div>
        ))}
        {!loading && matches.length === 0 && !error && (
          <p className="text-slate-500">No matches yet — run the graph from /admin first.</p>
        )}
      </div>
    </main>
  );
}