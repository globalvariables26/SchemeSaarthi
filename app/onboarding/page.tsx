"use client";
import { useState } from "react";
import { useCitizen } from "@/lib/useCitizen";
import { supabase } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const FIELDS = [
  "age", "income", "category", "state", "gender", "occupation", "disability_status",
];

function CreateProfileForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [incomeHint, setIncomeHint] = useState<any>(null);

  async function checkStateIncome(state: string) {
    if (!state) { setIncomeHint(null); return; }
    try {
      const res = await fetch(`${BACKEND_URL}/api/demographics/agricultural-income?state=${encodeURIComponent(state)}`);
      if (res.ok) setIncomeHint(await res.json());
      else setIncomeHint(null);
    } catch { setIncomeHint(null); }
  }

  async function submit() {
    setSaving(true);
    const { data: { session } } = await supabase.auth.getSession();
    await fetch(`${BACKEND_URL}/api/auth/register-citizen`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session?.access_token}`,
      },
      body: JSON.stringify({ display_name: name || "Citizen", attributes: values }),
    });
    onDone();
  }

  return (
    <div className="max-w-md space-y-3">
      <h1 className="text-2xl font-bold mb-4">Create Your Profile</h1>
      <input
        className="border rounded px-3 py-2 w-full"
        placeholder="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />

      {FIELDS.map((f) => (
        <input
          key={f}
          className="border rounded px-3 py-2 w-full"
          placeholder={f.replace(/_/g, " ")}
          value={values[f] || ""}
          onChange={(e) => setValues({ ...values, [f]: e.target.value })}
          onBlur={(e) => f === "state" && checkStateIncome(e.target.value)}
        />
      ))}


      {values.state && incomeHint && (
        <div className="text-xs text-slate-500 bg-slate-50 border rounded p-3">
          Average monthly agricultural household income in {incomeHint.state}: ₹
          {incomeHint.average_monthly_income.toLocaleString()}
          <br />
          <span className="text-slate-400">Source: {incomeHint.source}</span>
        </div>
      )}      

      <button
        disabled={saving}
        className="bg-emerald-600 text-white px-4 py-2 rounded w-full"
        onClick={submit}
      >
        {saving ? "Saving…" : "Create Profile"}
      </button>
    </div>
  );
}

export default function OnboardingPage() {
  const { citizenId, loading, needsProfile } = useCitizen();
  const [justRegistered, setJustRegistered] = useState(false);

  if (loading) return <main className="p-8">Loading…</main>;

  if (needsProfile && !justRegistered) {
    return (
      <main className="p-8">
        <CreateProfileForm onDone={() => setJustRegistered(true)} />
      </main>
    );
  }

  if (justRegistered) {
    return (
      <main className="p-8">
        <p className="text-emerald-700">
	  Profile created! Go to <a href="/" className="underline">the homepage</a> and use the menu to explore.
        </p>
      </main>
    );
  }

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Consent Center</h1>
      <p className="text-slate-500">Your citizen ID: {citizenId}</p>
      <p className="text-sm text-slate-400 mt-2">
        (Consent toggle list — same as before — goes here, now scoped to your own profile.)
      </p>
    </main>
  );
}