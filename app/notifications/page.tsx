"use client";
import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const DEMO_CITIZEN_ID = "76f2232e-9707-4a2a-8298-1f8facbb6200";

type Notification = {
  id: string;
  type: string;
  message: string;
  delivery_status: string;
  created_at: string;
};

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/citizen/${DEMO_CITIZEN_ID}/notifications`)
      .then((res) => res.json())
      .then(setItems)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Notifications</h1>
      {loading && <p>Loading…</p>}
      <ul className="space-y-3">
        {items.map((n) => (
          <li key={n.id} className="border-l-4 border-emerald-500 pl-4 py-1">
            <p className="text-sm text-slate-400">
              {new Date(n.created_at).toLocaleString()} · {n.type.replace(/_/g, " ")}
              {n.delivery_status === "escalated" && (
                <span className="ml-2 text-rose-600 font-medium">(delivery escalated)</span>
              )}
            </p>
            <p>{n.message}</p>
          </li>
        ))}
        {!loading && items.length === 0 && (
          <p className="text-slate-500">No notifications yet.</p>
        )}
      </ul>
    </main>
  );
}