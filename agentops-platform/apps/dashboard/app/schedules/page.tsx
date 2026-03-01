import Link from "next/link";

type ScheduleItem = {
  id: string;
  name: string;
  template_name: string;
  template_version: string | null;
  rrule_text: string;
  is_active: boolean;
  next_run_at: string | null;
};

type TemplateItem = { name: string; default_version?: string };

async function getSchedules(): Promise<ScheduleItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/schedules`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as ScheduleItem[];
}

async function getTemplates(): Promise<TemplateItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/templates`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()) as TemplateItem[];
}

export default async function SchedulesPage() {
  const [schedules, templates] = await Promise.all([getSchedules(), getTemplates()]);
  const defaultTemplate = templates[0]?.name ?? "sample_echo_task";

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>스케줄 관리</h1>
      <p style={{ marginTop: 0, color: "#334155" }}>예약 실행, 중지/재개, 즉시 실행을 관리합니다.</p>

      <div style={{ background: "#fff", borderRadius: 16, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>스케줄 생성</h2>
        <form action="/schedules/create" method="post" style={{ display: "grid", gap: "0.5rem", maxWidth: 720 }}>
          <input name="name" required placeholder="schedule name" style={{ padding: "0.5rem" }} />
          <select name="template_name" defaultValue={defaultTemplate} style={{ padding: "0.5rem" }}>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>
          <input name="template_version" placeholder="template version (선택)" style={{ padding: "0.5rem" }} />
          <input name="rrule_text" defaultValue="every:60" placeholder="every:60" style={{ padding: "0.5rem" }} />
          <textarea name="payload" rows={3} defaultValue='{"message":"scheduled"}' style={{ padding: "0.5rem", fontFamily: "monospace" }} />
          <button type="submit" style={{ width: 180, padding: "0.5rem" }}>생성</button>
        </form>
      </div>

      <div style={{ background: "#fff", borderRadius: 16, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>이름</th>
              <th style={{ padding: "0.75rem" }}>템플릿</th>
              <th style={{ padding: "0.75rem" }}>주기</th>
              <th style={{ padding: "0.75rem" }}>활성</th>
              <th style={{ padding: "0.75rem" }}>다음 실행</th>
              <th style={{ padding: "0.75rem" }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}><code>{s.name}</code></td>
                <td style={{ padding: "0.75rem" }}>{s.template_name}@{s.template_version ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>{s.rrule_text}</td>
                <td style={{ padding: "0.75rem" }}>{s.is_active ? "Y" : "N"}</td>
                <td style={{ padding: "0.75rem" }}>{s.next_run_at ?? "-"}</td>
                <td style={{ padding: "0.75rem" }}>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <form action={`/schedules/${s.id}/run-now`} method="post"><button type="submit">즉시실행</button></form>
                    {s.is_active ? (
                      <form action={`/schedules/${s.id}/pause`} method="post"><button type="submit">중지</button></form>
                    ) : (
                      <form action={`/schedules/${s.id}/resume`} method="post"><button type="submit">재개</button></form>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {schedules.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: "1rem", color: "#64748b" }}>스케줄이 없습니다.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <Link href="/runs/search">실행 검색으로 이동</Link>
      </div>
    </main>
  );
}
