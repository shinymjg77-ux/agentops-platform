import Link from "next/link";

type SearchResultItem = {
  run_id: string;
  task_id: string;
  template_name: string;
  template_version: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error_code: string | null;
  error_message: string | null;
};

type SearchResponse = {
  total: number;
  limit: number;
  offset: number;
  items: SearchResultItem[];
};

async function searchRuns(queryString: string): Promise<SearchResponse | null> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const qs = queryString.length > 0 ? `?${queryString}` : "";
  const res = await fetch(`${baseUrl}/v1/search/runs${qs}`, { cache: "no-store" });
  if (!res.ok) {
    return null;
  }
  return (await res.json()) as SearchResponse;
}

export default async function RunsSearchPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string; to?: string; status?: string; template_name?: string; template_version?: string; error_keyword?: string; limit?: string; offset?: string }>;
}) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v && v.length > 0) query.set(k, v);
  }

  if (!query.has("limit")) query.set("limit", "50");
  const data = await searchRuns(query.toString());

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>실행 검색</h1>
      <p style={{ marginTop: 0, color: "#4b5563" }}>기간/상태/템플릿/오류 기준으로 실행 이력을 검색합니다.</p>

      <div style={{ background: "#fff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <form method="get" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: "0.5rem" }}>
          <input type="datetime-local" name="from" defaultValue={params.from ?? ""} style={{ padding: "0.5rem" }} />
          <input type="datetime-local" name="to" defaultValue={params.to ?? ""} style={{ padding: "0.5rem" }} />
          <input name="status" defaultValue={params.status ?? ""} placeholder="status (success/failure)" style={{ padding: "0.5rem" }} />
          <input name="template_name" defaultValue={params.template_name ?? ""} placeholder="template_name" style={{ padding: "0.5rem" }} />
          <input name="template_version" defaultValue={params.template_version ?? ""} placeholder="template_version" style={{ padding: "0.5rem" }} />
          <input name="error_keyword" defaultValue={params.error_keyword ?? ""} placeholder="error_keyword" style={{ padding: "0.5rem" }} />
          <input name="limit" defaultValue={params.limit ?? "50"} placeholder="limit" style={{ padding: "0.5rem" }} />
          <input name="offset" defaultValue={params.offset ?? "0"} placeholder="offset" style={{ padding: "0.5rem" }} />
          <button type="submit" style={{ padding: "0.5rem" }}>검색</button>
        </form>
      </div>

      <div style={{ marginBottom: "0.75rem", color: "#374151" }}>
        검색건수: <strong>{data?.total ?? 0}</strong>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>run_id</th>
              <th style={{ padding: "0.75rem" }}>template</th>
              <th style={{ padding: "0.75rem" }}>version</th>
              <th style={{ padding: "0.75rem" }}>status</th>
              <th style={{ padding: "0.75rem" }}>started</th>
              <th style={{ padding: "0.75rem" }}>duration(ms)</th>
              <th style={{ padding: "0.75rem" }}>error</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((item) => (
              <tr key={item.run_id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}>
                  <div><code>{item.run_id}</code></div>
                  <div style={{ marginTop: "0.25rem" }}>
                    <Link href={`/tasks/${item.task_id}?run_id=${item.run_id}`}>상세</Link>
                  </div>
                </td>
                <td style={{ padding: "0.75rem" }}>{item.template_name}</td>
                <td style={{ padding: "0.75rem" }}>{item.template_version ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{item.status}</td>
                <td style={{ padding: "0.75rem" }}>{item.started_at}</td>
                <td style={{ padding: "0.75rem" }}>{item.duration_ms ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{item.error_message ?? item.error_code ?? "-"}</td>
              </tr>
            ))}
            {!data || data.items.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "1rem", color: "#6b7280" }}>
                  검색 결과가 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
