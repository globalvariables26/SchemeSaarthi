"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const router = useRouter();

  async function submit() {
    setError("");
    setInfo("");
    await supabase.auth.signOut();

    if (mode === "signup") {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) { setError(error.message); return; }
      if (!data.session) {
        setInfo("Account created — check your email to confirm, then log in.");
        setMode("login");
        return;
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) { setError(error.message); return; }
    }
    router.push("/");
  }

  return (
    <main className="min-h-screen bg-ink flex items-center justify-center px-6">
      <div className="bg-paper w-full max-w-sm p-10 rounded-sm">
        <h1 className="font-serif text-3xl mb-1">SchemeSaarthi</h1>
        <p className="text-ink/60 text-sm mb-8">{mode === "login" ? "Welcome back." : "Let's set you up."}</p>
        <input
          className="border border-ink/20 bg-white rounded-sm px-3 py-2 w-full mb-3 focus:outline-none focus:border-marigold"
          placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="border border-ink/20 bg-white rounded-sm px-3 py-2 w-full mb-4 focus:outline-none focus:border-marigold"
          type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-rust text-sm mb-3">{error}</p>}
        {info && <p className="text-banyan text-sm mb-3">{info}</p>}
        <button onClick={submit} className="bg-ink text-paper w-full py-3 rounded-sm font-medium hover:bg-ink/90">
          {mode === "login" ? "Log in" : "Sign up"}
        </button>
        <button onClick={() => setMode(mode === "login" ? "signup" : "login")} className="text-sm text-ink/50 mt-4 underline block">
          {mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in"}
        </button>
      </div>
    </main>
  );
}