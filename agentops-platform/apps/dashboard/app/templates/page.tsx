import Link from "next/link";

type TemplateItem = {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_active: boolean;
  default_version: string | null;
  updated_at: string;
};

async function getTemplates(): Promise<TemplateItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/template-registry?active_only=false`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  return (await res.json()) as TemplateItem[];
}

export default async function TemplateRegistryPage() {
  const templates = await getTemplates();

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>템플릿 레지스트리</h1>
      <p style={{ marginTop: 0, color: "#4b5563" }}>템플릿/버전 등록 및 기본버전 관리를 수행합니다.</p>

      <div style={{ background: "#fff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>템플릿 생성</h2>
        <form action="/templates/create" method="post" style={{ display: "grid", gap: "0.5rem", maxWidth: 560 }}>
          <input name="name" placeholder="name (예: nail_track_task)" required style={{ padding: "0.5rem" }} />
          <input name="display_name" placeholder="표시 이름" required style={{ padding: "0.5rem" }} />
          <input name="description" placeholder="설명(선택)" style={{ padding: "0.5rem" }} />
          <button type="submit" style={{ width: 160, padding: "0.5rem" }}>
            생성
          </button>
        </form>
      </div>

      <div style={{ background: "#fff", borderRadius: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>Name</th>
              <th style={{ padding: "0.75rem" }}>표시명</th>
              <th style={{ padding: "0.75rem" }}>기본버전</th>
              <th style={{ padding: "0.75rem" }}>활성</th>
              <th style={{ padding: "0.75rem" }}>수정시각</th>
              <th style={{ padding: "0.75rem" }}>상세</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}><code>{t.name}</code></td>
                <td style={{ padding: "0.75rem" }}>{t.display_name}</td>
                <td style={{ padding: "0.75rem" }}>{t.default_version ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{t.is_active ? "Y" : "N"}</td>
                <td style={{ padding: "0.75rem" }}>{t.updated_at}</td>
                <td style={{ padding: "0.75rem" }}><Link href={`/templates/${t.id}`}>열기</Link></td>
              </tr>
            ))}
            {templates.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "1rem", color: "#6b7280" }}>
                  등록된 템플릿이 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
