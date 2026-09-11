"use client";
import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const DEMO_CITIZEN_ID = "76f2232e-9707-4a2a-8298-1f8facbb6200";

type HeldDoc = {
  id: string;
  document_type: string;
  status: string;
  expiry_date?: string;
  issuing_authority?: string;
};

export default function DocumentsPage() {
  const [held, setHeld] = useState<HeldDoc[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/citizen/${DEMO_CITIZEN_ID}/documents`)
      .then((res) => res.json())
      .then((data) => setHeld(data.held || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Document Vault</h1>
      {loading && <p>Loading…</p>}
      <div className="space-y-3">
        {held.map((d) => (
          <div key={d.id} className="border rounded-lg p-4 flex justify-between items-center">
            <div>
              <p className="font-medium">{d.document_type.replace(/_/g, " ")}</p>
              <p className="text-sm text-slate-500">
                Issued by: {d.issuing_authority || "—"} · Expires: {d.expiry_date || "—"}
              </p>
            </div>
            <span
              className={`text-xs px-2 py-1 rounded-full border ${
                d.status === "expired"
                  ? "bg-rose-100 text-rose-800 border-rose-300"
                  : "bg-emerald-100 text-emerald-800 border-emerald-300"
              }`}
            >
              {d.status}
            </span>
          </div>
        ))}
        {!loading && held.length === 0 && (
          <p className="text-slate-500">No documents on file yet.</p>
        )}
      </div>
      <p className="text-sm text-slate-500 mt-6">
        Missing-document checklists appear after running the graph from /admin — check the
        notifications feed for the acquisition steps.
      </p>
    </main>
  );
}