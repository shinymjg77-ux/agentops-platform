import Link from "next/link";

type TemplateVersion = {
  version: string;
  adapter_name: string;
  adapter_version: string | null;
  input_schema: Record<string, unknown>;
  retry_policy: Record<string, unknown> | null;
  timeout_sec: number | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
};

type TemplateDetail = {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_active: boolean;
  versions: TemplateVersion[];
};

async function getTemplate(templateId: string): Promise<TemplateDetail | null> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/template-registry/${templateId}`, { cache: "no-store" });
  if (!res.ok) {
    return null;
  }
  return (await res.json()) as TemplateDetail;
}

export default async function TemplateDetailPage({ params }: { params: Promise<{ templateId: string }> }) {
  const { templateId } = await params;
  const data = await getTemplate(templateId);

  if (!data) {
    return (
      <main style={{ maxWidth: 1100, margin: "0 auto" }}>
        <h1>템플릿 상세</h1>
        <p>템플릿을 찾을 수 없습니다.</p>
        <Link href="/templates">목록으로</Link>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>템플릿 상세</h1>
      <p style={{ marginTop: 0, color: "#4b5563" }}>
        <code>{data.name}</code> ({data.display_name})
      </p>

      <div style={{ background: "#fff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <div><strong>설명:</strong> {data.description ?? "-"}</div>
        <div><strong>활성:</strong> {data.is_active ? "Y" : "N"}</div>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>버전 추가</h2>
        <form
          action={`/templates/${templateId}/versions/create`}
          method="post"
          style={{ display: "grid", gap: "0.5rem", maxWidth: 700 }}
        >
          <input name="version" placeholder="version (예: 1.1.0)" required style={{ padding: "0.5rem" }} />
          <input
            name="adapter_name"
            placeholder="adapter_name (예: tasks.sample_echo_task)"
            required
            style={{ padding: "0.5rem" }}
          />
          <input name="adapter_version" placeholder="adapter_version (선택)" style={{ padding: "0.5rem" }} />
          <textarea
            name="input_schema"
            placeholder='input_schema JSON (예: {"type":"object"})'
            rows={4}
            style={{ padding: "0.5rem", fontFamily: "monospace" }}
          />
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input type="checkbox" name="set_default" value="1" />
            기본 버전으로 설정
          </label>
          <button type="submit" style={{ width: 180, padding: "0.5rem" }}>
            버전 추가
          </button>
        </form>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, overflowX: "auto", marginBottom: "1rem" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>버전</th>
              <th style={{ padding: "0.75rem" }}>어댑터</th>
              <th style={{ padding: "0.75rem" }}>어댑터버전</th>
              <th style={{ padding: "0.75rem" }}>기본</th>
              <th style={{ padding: "0.75rem" }}>활성</th>
              <th style={{ padding: "0.75rem" }}>동작</th>
            </tr>
          </thead>
          <tbody>
            {data.versions.map((v) => (
              <tr key={v.version} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}><code>{v.version}</code></td>
                <td style={{ padding: "0.75rem" }}>{v.adapter_name}</td>
                <td style={{ padding: "0.75rem" }}>{v.adapter_version ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{v.is_default ? "Y" : "N"}</td>
                <td style={{ padding: "0.75rem" }}>{v.is_active ? "Y" : "N"}</td>
                <td style={{ padding: "0.75rem" }}>
                  {v.is_default ? (
                    <span style={{ color: "#6b7280" }}>기본</span>
                  ) : (
                    <form action={`/templates/${templateId}/versions/${encodeURIComponent(v.version)}/set-default`} method="post">
                      <button type="submit">기본으로</button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
            {data.versions.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "1rem", color: "#6b7280" }}>
                  등록된 버전이 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Link href="/templates">목록으로</Link>
    </main>
  );
}
