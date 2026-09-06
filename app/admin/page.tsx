"use client";

// Admin / Demo Control Panel — Owner: Sher.
// This is the screen the audience watches during the live failure-injection demo moment.
// It must show, on screen, the plan visibly changing — not just a console log.
//
// Requires the backend running locally at NEXT_PUBLIC_BACKEND_URL (default http://localhost:8000)
// and DEMO_CITIZEN_ID set below to the id printed by `python db/seed.py`.

import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// TODO(Sher/Jaya): replace with the real seeded citizen_id, or load it from a config endpoint.
const DEMO_CITIZEN_ID = "REPLACE_WITH_SEEDED_CITIZEN_ID";

type GraphEvent = {
  type: string;
  [key: string]: unknown;
};

export default function AdminPage() {
  const [events, setEvents] = useState<GraphEvent[]>([]);
  const [sourceOffline, setSourceOffline] = useState(false);
  const [deliveryFailure, setDeliveryFailure] = useState(false);

  useEffect(() => {
    const source = new EventSource(`${BACKEND_URL}/api/graph-events`);
    source.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [data, ...prev].slice(0, 50));
    };
    return () => source.close();
  }, []);

  async function post(path: string, body: object) {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  }

  return (
    <main className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">SchemeSaarthi — Demo Control Panel</h1>

      <div className="flex flex-wrap gap-3">
        <button
          className="px-4 py-2 rounded bg-emerald-600 text-white"
          onClick={() =>
            post("/api/admin/inject-scheme", {
              citizen_id: DEMO_CITIZEN_ID,
              payload: {
                name: "New Emergency Relief Grant",
                description: "Injected live during demo.",
                criteria: { income_ceiling: 300000, state: "Odisha" },
                required_documents: ["income_certificate"],
                authority_level: "state",
              },
            })
          }
        >
          Inject New Scheme
        </button>

        <button
          className="px-4 py-2 rounded bg-amber-600 text-white"
          onClick={async () => {
            const next = !sourceOffline;
            await post("/api/admin/toggle-source-offline", { offline: next });
            setSourceOffline(next);
          }}
        >
          {sourceOffline ? "Bring Source Online" : "Take Source Offline"}
        </button>

        <button
          className="px-4 py-2 rounded bg-rose-600 text-white"
          onClick={async () => {
            const next = !deliveryFailure;
            await post("/api/admin/toggle-delivery-failure", { simulate_failure: next });
            setDeliveryFailure(next);
          }}
        >
          {deliveryFailure ? "Stop Simulating Delivery Failure" : "Simulate Delivery Failure"}
        </button>

        <button
          className="px-4 py-2 rounded bg-slate-700 text-white"
          onClick={() => post("/api/graph/run", { citizen_id: DEMO_CITIZEN_ID, trigger: "manual_demo_trigger" })}
        >
          Run Full Graph Now
        </button>
      </div>

      {/*
        TODO(Sher): replace this raw event list with an actual animated node-graph diagram
        (motion.dev / framer-motion) that highlights the active node and draws an edge
        animation when a `plan_change` event arrives — that visual IS the demo's core moment.
      */}
      <section>
        <h2 className="text-lg font-semibold mb-2">Live graph events</h2>
        <ul className="space-y-1 font-mono text-sm">
          {events.map((ev, i) => (
            <li
              key={i}
              className={ev.type === "plan_change" ? "text-rose-600 font-bold" : "text-slate-700"}
            >
              {JSON.stringify(ev)}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
