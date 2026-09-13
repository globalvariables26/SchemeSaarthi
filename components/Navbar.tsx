"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/notifications", label: "Missing Documents" },
  { href: "/explore", label: "Why Not Matched" },
  { href: "/onboarding", label: "Consent" },
  { href: "/profile", label: "Profile" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  if (pathname === "/login") return null;

  async function logout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <nav className="bg-ink text-paper px-8 py-4 flex items-center gap-8">
      <Link href="/" className="font-serif text-xl tracking-tight">
        Scheme<span className="text-marigold">Saarthi</span>
      </Link>
      <div className="flex gap-6 text-sm">
        {LINKS.map((l) => {
          const active = pathname === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`pb-1 border-b-2 transition-colors ${
                active ? "border-marigold text-white" : "border-transparent text-paper/60 hover:text-paper"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </div>
      <button onClick={logout} className="ml-auto text-sm text-paper/60 hover:text-marigold">
        Log out
      </button>
    </nav>
  );
}