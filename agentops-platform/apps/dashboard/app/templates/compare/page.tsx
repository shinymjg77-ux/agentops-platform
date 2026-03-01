type TemplateRow = {
  id: string;
  name: string;
  display_name: string;
};

type AnalyticsRow = {
  template_version: string;
  total_runs: number;
  success_rate: number;
  failure_rate: number;
  avg_duration_ms: number | null;
  p95_duration_ms: number | null;
};

type AnalyticsResponse = {
  template_name: string;
  from: string | null;
  to: string | null;
  versions: string[] | null;
  items: AnalyticsRow[];
};

async function getTemplates(): Promise<TemplateRow[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/template-registry`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as TemplateRow[];
}

async function getAnalytics(query: string): Promise<AnalyticsResponse | null> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/analytics/template-versions?${query}`, { cache: "no-store" });
  if (!res.ok) return null;
  return (await res.json()) as AnalyticsResponse;
}

export default async function TemplateComparePage({
  searchParams,
}: {
  searchParams: Promise<{ template_name?: string; from?: string; to?: string; versions?: string }>;
}) {
  const params = await searchParams;
  const templates = await getTemplates();

  const query = new URLSearchParams();
  if (params.template_name) query.set("template_name", params.template_name);
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);
  if (params.versions) query.set("versions", params.versions);

  const data = params.template_name ? await getAnalytics(query.toString()) : null;

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>버전 비교</h1>
      <p style={{ marginTop: 0, color: "#4b5563" }}>템플릿 버전별 성공률/실패율/실행시간을 비교합니다.</p>

      <div style={{ background: "#fff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <form method="get" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: "0.5rem" }}>
          <select name="template_name" defaultValue={params.template_name ?? ""} style={{ padding: "0.5rem" }}>
            <option value="">템플릿 선택</option>
            {templates.map((t) => (
              <option key={t.id} value={t.name}>{t.display_name} ({t.name})</option>
            ))}
          </select>
          <input type="datetime-local" name="from" defaultValue={params.from ?? ""} style={{ padding: "0.5rem" }} />
          <input type="datetime-local" name="to" defaultValue={params.to ?? ""} style={{ padding: "0.5rem" }} />
          <input name="versions" defaultValue={params.versions ?? ""} placeholder="versions (예: 1.0.0,1.1.0)" style={{ padding: "0.5rem" }} />
          <button type="submit" style={{ padding: "0.5rem", width: 140 }}>비교</button>
        </form>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>버전</th>
              <th style={{ padding: "0.75rem" }}>실행수</th>
              <th style={{ padding: "0.75rem" }}>성공률(%)</th>
              <th style={{ padding: "0.75rem" }}>실패율(%)</th>
              <th style={{ padding: "0.75rem" }}>평균(ms)</th>
              <th style={{ padding: "0.75rem" }}>P95(ms)</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((row) => (
              <tr key={row.template_version} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}><code>{row.template_version}</code></td>
                <td style={{ padding: "0.75rem" }}>{row.total_runs}</td>
                <td style={{ padding: "0.75rem" }}>{row.success_rate}</td>
                <td style={{ padding: "0.75rem" }}>{row.failure_rate}</td>
                <td style={{ padding: "0.75rem" }}>{row.avg_duration_ms?.toFixed(2) ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{row.p95_duration_ms?.toFixed(2) ?? "-"}</td>
              </tr>
            ))}
            {!data || data.items.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "1rem", color: "#6b7280" }}>
                  비교 결과가 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
