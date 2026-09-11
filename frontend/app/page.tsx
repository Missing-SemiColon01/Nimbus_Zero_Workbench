"use client";

import { FormEvent, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function Home() {
  const [request, setRequest] = useState("");
  const [result, setResult] = useState<string>("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setResult("Planning locally…");
    try {
      const response = await fetch(`${apiBase}/tasks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request }) });
      const data = await response.json();
      setResult(response.ok ? `Task ${data.task_id}\nModel: ${data.selected_model}\nPlan: ${data.plan.join(" → ")}` : data.detail);
    } catch { setResult("The local API is unavailable."); }
  }
  return <main><p className="eyebrow">SOVEREIGN MODE · ENABLED</p><h1>Agentic AI Workbench</h1><p>Local inference, controlled tools, and auditable artifacts.</p><form onSubmit={submit}><label htmlFor="request">Delegate a task</label><textarea id="request" value={request} onChange={(e) => setRequest(e.target.value)} placeholder="Analyse an inspection report…" required /><button type="submit">Create task</button></form>{result && <pre>{result}</pre>}<footer>External AI calls: 0 · Network egress: blocked by deployment policy</footer></main>;
}
