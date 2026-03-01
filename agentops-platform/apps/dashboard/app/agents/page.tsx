
type AgentItem = {
  id: string;
  name: string;
  hostname: string | null;
  status: string;
  last_heartbeat_at: string;
  capacity: number;
  queue_names: string[];
};

async function getAgents(): Promise<AgentItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/agents`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as AgentItem[];
}

function statusColor(status: string): string {
  if (status === "online") return "#166534";
  if (status === "degraded") return "#b45309";
  return "#991b1b";
}

export default async function AgentsPage() {
  const agents = await getAgents();

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>에이전트 상태</h1>
      <p style={{ marginTop: 0, color: "#334155" }}>워커 노드 heartbeat 및 용량 상태를 확인합니다.</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
        {agents.map((a) => (
          <section key={a.id} style={{ background: "#fff", borderRadius: 14, padding: "1rem", border: "1px solid #e2e8f0" }}>
            <h2 style={{ marginTop: 0, marginBottom: "0.35rem", fontSize: "1rem" }}><code>{a.name}</code></h2>
            <div style={{ color: statusColor(a.status), fontWeight: 700, marginBottom: "0.5rem" }}>{a.status}</div>
            <div><strong>host:</strong> {a.hostname ?? "-"}</div>
            <div><strong>last heartbeat:</strong> {a.last_heartbeat_at}</div>
            <div><strong>capacity:</strong> {a.capacity}</div>
            <div><strong>queues:</strong> {a.queue_names.join(", ")}</div>
          </section>
        ))}
        {agents.length === 0 ? (
          <section style={{ background: "#fff", borderRadius: 14, padding: "1rem", color: "#64748b" }}>
            heartbeat 데이터가 없습니다.
          </section>
        ) : null}
      </div>
    </main>
  );
}
