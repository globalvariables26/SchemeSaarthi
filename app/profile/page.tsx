"use client";
import { useEffect, useState } from "react";
import { useCitizen } from "@/lib/useCitizen";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Attribute = {
  id: string;
  attribute_key: string;
  attribute_value: string;
};

export default function ProfilePage() {
  const { citizenId, loading: authLoading } = useCitizen();
  const [attrs, setAttrs] = useState<Attribute[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  function load() {
    if (!citizenId) return;
    fetch(`${BACKEND_URL}/api/citizen/${citizenId}/attributes`)
      .then((res) => res.json())
      .then(setAttrs)
      .finally(() => setLoading(false));
  }

  useEffect(load, [citizenId]);

  async function save(id: string) {
    await fetch(`${BACKEND_URL}/api/attributes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attribute_value: editValue }),
    });
    setEditingId(null);
    load();
  }

  if (authLoading || !citizenId) return <main className="p-8">Loading…</main>;

  return (
    <main className="p-8 max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Your Profile</h1>
      {loading && <p>Loading…</p>}
      <div className="space-y-3">
        {attrs.map((a) => (
          <div key={a.id} className="border rounded-lg p-4 flex justify-between items-center">
            <span className="capitalize text-slate-500">{a.attribute_key.replace(/_/g, " ")}</span>
            {editingId === a.id ? (
              <div className="flex gap-2">
                <input
                  className="border rounded px-2 py-1 w-32"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                />
                <button className="text-emerald-700 font-medium" onClick={() => save(a.id)}>Save</button>
              </div>
            ) : (
              <button
                className="font-medium hover:underline"
                onClick={() => { setEditingId(a.id); setEditValue(a.attribute_value); }}
              >
                {a.attribute_value} ✎
              </button>
            )}
          </div>
        ))}
      </div>
    </main>
  );
}