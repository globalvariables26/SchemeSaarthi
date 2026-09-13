"use client";
import { useCitizen } from "@/lib/useCitizen";
import Link from "next/link";

const CARDS = [
  { href: "/dashboard", title: "Matched Schemes", desc: "See what you currently qualify for, and why." },
  { href: "/documents", title: "Documents", desc: "Store your papers once — access them anywhere." },
  { href: "/notifications", title: "Missing Documents", desc: "Know exactly what's still outstanding." },
  { href: "/explore", title: "Why Not Matched", desc: "Look up any scheme and see the exact blocker." },
  { href: "/profile", title: "Profile", desc: "Keep your details current as your life changes." },
  { href: "/onboarding", title: "Consent", desc: "Control exactly what data is used, and why." },
];

export default function Home() {
  const { needsProfile, loading } = useCitizen();
  if (loading) return <main className="p-10 font-serif text-xl">Loading…</main>;

  if (needsProfile) {
    return (
      <main className="max-w-xl mx-auto px-8 py-24 text-center">
        <h1 className="font-serif text-5xl leading-tight mb-4">Let's get you started.</h1>
        <p className="text-ink/70 mb-8">A short profile is all it takes for SchemeSaarthi to start watching on your behalf.</p>
        <Link href="/onboarding" className="inline-block bg-marigold text-ink font-medium px-6 py-3 rounded-sm hover:bg-marigold/90">
          Create your profile
        </Link>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto px-8 py-16">
      <p className="text-marigold font-medium mb-2">Welcome back</p>
      <h1 className="font-serif text-5xl leading-tight mb-14 max-w-2xl">
        Here's everything your guide is watching for you.
      </h1>
      <div className="grid sm:grid-cols-2 gap-px bg-ink/10">
        {CARDS.map((c) => (
          <Link key={c.href} href={c.href} className="bg-paper p-8 hover:bg-sand transition-colors">
            <h2 className="font-serif text-2xl mb-2">{c.title}</h2>
            <p className="text-ink/60 text-sm">{c.desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}