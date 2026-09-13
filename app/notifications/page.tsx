"use client";
import { useEffect, useState } from "react";
import { useCitizen } from "@/lib/useCitizen";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type MissingDoc = { document_type: string; why_required: string; checklist: string[] };

export default function NotificationsPage() {
  const { citizenId, loading: authLoading } = useCitizen();
  const [missing, setMissing] = useState<MissingDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [openType, setOpenType] = useState<string | null>(null);

  useEffect(() => {
    if (!citizenId) return;
    fetch(`${BACKEND_URL}/api/citizen/${citizenId}/missing-documents`)
      .then((res) => res.json())
      .then(setMissing)
      .finally(() => setLoading(false));
  }, [citizenId]);

  if (authLoading || !citizenId) return <main className="p-8">Loading…</main>;

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-2">Documents You're Missing</h1>
      <p className="text-slate-500 mb-6">Checked against the internet every 2 days. Upload from the Documents page to clear one.</p>
      {loading && <p>Checking…</p>}
      {!loading && missing.length === 0 && <p className="text-emerald-700">You're all caught up.</p>}
      <ul className="space-y-3">
        {missing.map((d) => {
          const isOpen = openType === d.document_type;
          return (
            <li key={d.document_type} className="border-l-4 border-amber-500 pl-4 py-2">
              <p className="cursor-pointer font-medium hover:underline" onClick={() => setOpenType(isOpen ? null : d.document_type)}>
                {d.document_type.replace(/_/g, " ")}
                <span className="text-amber-700 text-sm ml-2">{isOpen ? "▲ hide steps" : "▼ view steps"}</span>
              </p>
              <p className="text-sm text-slate-500">{d.why_required}</p>
              {isOpen && (
                <ol className="list-decimal list-inside mt-2 bg-slate-50 rounded p-3 text-sm space-y-1">
                  {d.checklist.map((step, i) => <li key={i}>{step}</li>)}
                </ol>
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}