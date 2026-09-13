"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "./supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useCitizen() {
  const [citizenId, setCitizenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsProfile, setNeedsProfile] = useState(false);
  const router = useRouter();

  useEffect(() => {
    (async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/login");
        return;
      }
      const res = await fetch(`${BACKEND_URL}/api/auth/my-citizen-id`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.status === 404) {
        setNeedsProfile(true);
        setLoading(false);
        return;
      }
      const data = await res.json();
      setCitizenId(data.citizen_id);
      setLoading(false);
    })();
  }, []);

  return { citizenId, loading, needsProfile };
}