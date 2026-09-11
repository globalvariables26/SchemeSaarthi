"use client";
import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const DEMO_CITIZEN_ID = "76f2232e-9707-4a2a-8298-1f8facbb6200";

type Attribute = {
  id: string;
  attribute_key: string;
  attribute_value: string;
  consent_purpose: string;
  consent_granted: boolean;
  revoked_at: string | null;
};

export default function OnboardingPage() {
  const [attrs, setAttrs] = useState<Attribute[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    fetch(`${BACKEND_URL}/api/citizen/${DEMO_CITIZEN_ID}/attributes`)
      .then((res) => res.json())
      .then(setAttrs)
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function revoke(attributeId: string) {
    await fetch(`${BACKEND_URL}/api/consent/${attributeId}/revoke`, { method: "POST" });
    load();
  }

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Consent Center</h1>
      {loading && <p>Loading…</p>}
      <div className="space-y-3">
        {attrs.map((a) => {
          const active = a.consent_granted && !a.revoked_at;
          return (
            <div key={a.id} className="border rounded-lg p-4 flex justify-between items-center">
              <div>
                <p className="font-medium capitalize">{a.attribute_key.replace(/_/g, " ")}</p>
                <p className="text-sm text-slate-500">Purpose: {a.consent_purpose}</p>
              </div>
              <button
                disabled={!active}
                onClick={() => revoke(a.id)}
                className={`text-xs px-3 py-1.5 rounded-full border ${
                  active
                    ? "bg-white border-rose-300 text-rose-700 hover:bg-rose-50"
                    : "bg-slate-100 border-slate-200 text-slate-400"
                }`}
              >
                {active ? "Revoke consent" : "Revoked"}
              </button>
            </div>
          );
        })}
      </div>
    </main>
  );
}