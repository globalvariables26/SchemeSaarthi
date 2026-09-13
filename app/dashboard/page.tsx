"use client";
import { useEffect, useState } from "react";
import { useCitizen } from "@/lib/useCitizen";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type MatchRow = {
  id: string; status: string; confidence: number; reasoning?: string; rejection_reason?: string;
  schemes?: { name: string; description: string };
  document_status?: { document_type: string; held: boolean }[];
};

const STATUS_STYLE: Record<string, { border: string; label: string }> = {
  matched: { border: "border-banyan", label: "text-banyan" },
  needs_document: { border: "border-marigold", label: "text-marigold" },
  conflicting: { border: "border-rust", label: "text-rust" },
  uncertain: { border: "border-ink/20", label: "text-ink/50" },
  rejected: { border: "border-ink/10", label: "text-ink/40" },
};

export default function DashboardPage() {
  const { citizenId, loading: authLoading } = useCitizen();
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    if (!citizenId) return;
    fetch(`${BACKEND_URL}/api/citizen/${citizenId}/matches`).then((r) => r.json()).then(setMatches).finally(() => setLoading(false));
  }, [citizenId]);

  if (authLoading || !citizenId) return <main className="p-10 font-serif text-xl">Loading…</main>;

  return (
    <main className="max-w-4xl mx-auto px-8 py-14">
      <h1 className="font-serif text-4xl mb-10">Your matched schemes</h1>
      {loading && <p>Loading…</p>}
      <div className="space-y-4">
        {matches.map((m) => {
          const isOpen = openId === m.id;
          const isMatched = m.status === "matched" || m.status === "needs_document";
          const style = STATUS_STYLE[m.status] || STATUS_STYLE.uncertain;
          return (
            <div key={m.id} className={`border-l-4 ${style.border} bg-white/60 cursor-pointer`} onClick={() => setOpenId(isOpen ? null : m.id)}>
              <div className="p-6">
                <div className="flex justify-between items-baseline">
                  <h2 className="font-serif text-2xl">{m.schemes?.name}</h2>
                  <span className={`text-sm font-medium ${style.label}`}>{m.status.replace("_", " ")}</span>
                </div>
                <p className="text-ink/60 text-sm mt-1 max-w-2xl">{m.schemes?.description}</p>
                <p className="text-xs text-ink/40 mt-2">Confidence {Math.round((m.confidence || 0) * 100)}% — {isOpen ? "hide details" : "view details"}</p>
              </div>
              {isOpen && (
                <div className="px-6 pb-6 text-sm space-y-3 border-t border-ink/10 pt-4" onClick={(e) => e.stopPropagation()}>
                  {isMatched ? (
                    <>
                      <p><span className="font-medium">Why you're eligible: </span>{m.reasoning}</p>
                      <div>
                        <p className="font-medium mb-1">To claim this benefit:</p>
                        <ul className="space-y-1">
                          {(m.document_status || []).map((d) => (
                            <li key={d.document_type} className="flex gap-2">
                              <span className={d.held ? "text-banyan" : "text-marigold"}>{d.held ? "✓" : "○"}</span>
                              {d.document_type.replace(/_/g, " ")}
                              {!d.held && <span className="text-xs text-marigold">— upload from Documents</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <p className="text-xs text-ink/40">Preliminary match only — visit the scheme's official portal to formally apply.</p>
                    </>
                  ) : (
                    <>
                      <p><span className="font-medium">Why you weren't matched: </span>{m.rejection_reason || m.reasoning}</p>
                      <p className="text-xs text-ink/40">
                        If this depends on something that can change, update it in your <a href="/profile" className="underline">Profile</a>.
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {!loading && matches.length === 0 && <p className="text-ink/50">No matches yet — run the graph from /admin first.</p>}
      </div>
    </main>
  );
}