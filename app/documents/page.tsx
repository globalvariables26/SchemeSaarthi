"use client";
import { useEffect, useState } from "react";
import { useCitizen } from "@/lib/useCitizen";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type HeldDoc = { id: string; document_type: string; status: string; expiry_date?: string; issuing_authority?: string; url?: string };
type RequiredDoc = { document_type: string; why_required: string };

export default function DocumentsPage() {
  const { citizenId, loading: authLoading } = useCitizen();
  const [held, setHeld] = useState<HeldDoc[]>([]);
  const [required, setRequired] = useState<RequiredDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [docType, setDocType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  function load() {
    if (!citizenId) return;
    Promise.all([
      fetch(`${BACKEND_URL}/api/citizen/${citizenId}/documents`).then((r) => r.json()),
      fetch(`${BACKEND_URL}/api/citizen/${citizenId}/required-documents`).then((r) => r.json()),
    ]).then(([docsData, reqData]) => {
      setHeld(docsData.held || []);
      setRequired(reqData || []);
      if (reqData?.length && !docType) setDocType(reqData[0].document_type);
    }).finally(() => setLoading(false));
  }

  useEffect(load, [citizenId]);

  async function upload() {
    if (!file || !citizenId || !docType) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("document_type", docType);
    formData.append("file", file);
    await fetch(`${BACKEND_URL}/api/citizen/${citizenId}/documents/upload`, { method: "POST", body: formData });
    setFile(null);
    setUploading(false);
    load();
  }

  if (authLoading || !citizenId) return <main className="p-8">Loading…</main>;

  return (
    <main className="p-8 space-y-10">
      <section>
        <h1 className="text-2xl font-bold mb-4">Upload a Document</h1>
        {required.length === 0 && !loading && (
          <p className="text-slate-500 text-sm mb-3">
            Still determining your required documents — check back shortly, or visit "Missing Documents."
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <select className="border rounded px-3 py-2" value={docType} onChange={(e) => setDocType(e.target.value)}>
            {required.map((r) => (
              <option key={r.document_type} value={r.document_type}>{r.document_type.replace(/_/g, " ")}</option>
            ))}
          </select>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button disabled={!file || uploading} onClick={upload} className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50">
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-bold mb-4">Your Documents</h2>
        {loading && <p>Loading…</p>}
        <div className="space-y-3">
          {held.map((d) => (
            <div key={d.id} className="border rounded-lg p-4 flex justify-between items-center">
              <div>
                <p className="font-medium">{d.document_type.replace(/_/g, " ")}</p>
                <p className="text-sm text-slate-500">
                  {d.issuing_authority ? `Issued by: ${d.issuing_authority} · ` : ""}
                  {d.expiry_date ? `Expires: ${d.expiry_date}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full border ${d.status === "expired" ? "bg-rose-100 text-rose-800 border-rose-300" : "bg-emerald-100 text-emerald-800 border-emerald-300"}`}>
                  {d.status}
                </span>
                {d.url && <a href={d.url} target="_blank" className="text-sm text-emerald-700 underline">View</a>}
              </div>
            </div>
          ))}
          {!loading && held.length === 0 && <p className="text-slate-500">No documents uploaded yet.</p>}
        </div>
      </section>
    </main>
  );
}