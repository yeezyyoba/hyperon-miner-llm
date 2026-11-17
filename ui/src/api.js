// Thin client for the FastAPI backend (minerllm/api/app.py).

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  datasets: () => request("/api/datasets"),
  providers: () => request("/api/providers"),
  replays: () => request("/api/replays"),
  results: () => request("/api/results"),
  usage: () => request("/api/usage"),
  startRun: (body) => request("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  cancelRun: (id) => request(`/api/runs/${id}/cancel`, { method: "POST" }),
};

const KINDS = ["started", "configure", "llm_batch", "select", "verify", "finish",
  "usage", "log", "result", "status"];

// Subscribe to a run's Server-Sent Events. Returns a function that closes the stream.
export function followRun(id, onEvent, onEnd) {
  const source = new EventSource(`/api/runs/${id}/events`);
  let last = -1;
  const handle = (msg) => {
    const e = JSON.parse(msg.data);
    if (e.seq <= last) return; // EventSource reconnects resend from Last-Event-ID; be safe
    last = e.seq;
    onEvent(e);
  };
  KINDS.forEach((k) => source.addEventListener(k, handle));
  source.addEventListener("end", () => {
    source.close();
    onEnd?.();
  });
  return () => source.close();
}
