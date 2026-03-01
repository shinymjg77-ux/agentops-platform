
type PolicyItem = {
  id: string;
  name: string;
  scope_type: string;
  scope_ref: string | null;
  metric_key: string;
  operator: string;
  threshold_value: number;
  action_type: string;
  is_active: boolean;
  last_triggered_at: string | null;
};

async function getPolicies(): Promise<PolicyItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/policies`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as PolicyItem[];
}

export default async function PoliciesPage() {
  const policies = await getPolicies();

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>정책 관리</h1>
      <p style={{ marginTop: 0, color: "#334155" }}>실패율/지연 기준 정책을 등록하고 자동 액션을 제어합니다.</p>

      <div style={{ background: "#fff", borderRadius: 16, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>정책 생성</h2>
        <form action="/policies/create" method="post" style={{ display: "grid", gap: "0.5rem", maxWidth: 740 }}>
          <input name="name" required placeholder="policy name" style={{ padding: "0.5rem" }} />
          <input name="scope_type" defaultValue="template" style={{ padding: "0.5rem" }} />
          <input name="scope_ref" placeholder="template name 또는 schedule name" style={{ padding: "0.5rem" }} />
          <input name="metric_key" defaultValue="failure_rate" style={{ padding: "0.5rem" }} />
          <input name="operator" defaultValue="gte" style={{ padding: "0.5rem" }} />
          <input name="threshold_value" defaultValue="50" style={{ padding: "0.5rem" }} />
          <input name="window_minutes" defaultValue="15" style={{ padding: "0.5rem" }} />
          <input name="cooldown_minutes" defaultValue="30" style={{ padding: "0.5rem" }} />
          <input name="action_type" defaultValue="pause_schedule" style={{ padding: "0.5rem" }} />
          <button type="submit" style={{ width: 180, padding: "0.5rem" }}>생성</button>
        </form>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>이름</th>
              <th style={{ padding: "0.75rem" }}>범위</th>
              <th style={{ padding: "0.75rem" }}>조건</th>
              <th style={{ padding: "0.75rem" }}>액션</th>
              <th style={{ padding: "0.75rem" }}>활성</th>
              <th style={{ padding: "0.75rem" }}>동작</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}><code>{p.name}</code></td>
                <td style={{ padding: "0.75rem" }}>{p.scope_type}:{p.scope_ref ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{p.metric_key} {p.operator} {p.threshold_value}</td>
                <td style={{ padding: "0.75rem" }}>{p.action_type}</td>
                <td style={{ padding: "0.75rem" }}>{p.is_active ? "Y" : "N"}</td>
                <td style={{ padding: "0.75rem" }}>
                  {p.is_active ? (
                    <form action={`/policies/${p.id}/disable`} method="post"><button type="submit">비활성</button></form>
                  ) : (
                    <form action={`/policies/${p.id}/enable`} method="post"><button type="submit">활성</button></form>
                  )}
                </td>
              </tr>
            ))}
            {policies.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: "1rem", color: "#64748b" }}>정책이 없습니다.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
