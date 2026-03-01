import Link from "next/link";

type TemplateItem = {
  name: string;
  display_name?: string;
};

type RunSearchResponse = {
  total: number;
  items: Array<{
    run_id: string;
    task_id: string;
    template_name: string;
    template_version: string | null;
    status: string;
    started_at: string;
  }>;
};

type ProjectBoard = {
  templateName: string;
  total: number;
  queued: number;
  started: number;
  retry: number;
  success: number;
  failure: number;
  recent: RunSearchResponse["items"];
};

async function getTemplates(): Promise<TemplateItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/template-registry`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = (await res.json()) as Array<{ name: string; display_name: string }>;
  return data.map((t) => ({ name: t.name, display_name: t.display_name }));
}

async function getCountByStatus(templateName: string, status?: string): Promise<number> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const query = new URLSearchParams();
  query.set("template_name", templateName);
  query.set("limit", "1");
  if (status) query.set("status", status);
  const res = await fetch(`${baseUrl}/v1/search/runs?${query.toString()}`, { cache: "no-store" });
  if (!res.ok) return 0;
  const data = (await res.json()) as RunSearchResponse;
  return data.total;
}

async function getRecentRuns(templateName: string): Promise<RunSearchResponse["items"]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const query = new URLSearchParams({ template_name: templateName, limit: "5" });
  const res = await fetch(`${baseUrl}/v1/search/runs?${query.toString()}`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = (await res.json()) as RunSearchResponse;
  return data.items;
}

async function buildBoard(templateName: string): Promise<ProjectBoard> {
  const [
    total,
    queued,
    started,
    retry,
    success,
    failure,
    recent,
  ] = await Promise.all([
    getCountByStatus(templateName),
    getCountByStatus(templateName, "queued"),
    getCountByStatus(templateName, "started"),
    getCountByStatus(templateName, "retry"),
    getCountByStatus(templateName, "success"),
    getCountByStatus(templateName, "failure"),
    getRecentRuns(templateName),
  ]);

  return { templateName, total, queued, started, retry, success, failure, recent };
}

export default async function ProjectsOverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ templates?: string }>;
}) {
  const params = await searchParams;
  const templates = await getTemplates();

  const selected = (params.templates ?? templates.slice(0, 3).map((t) => t.name).join(","))
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0)
    .slice(0, 3);

  const boards = await Promise.all(selected.map((name) => buildBoard(name)));

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto" }}>
      <header
        style={{
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 45%, #0b3b66 100%)",
          color: "#f8fafc",
          borderRadius: 20,
          padding: "1.2rem 1.25rem",
          boxShadow: "0 20px 40px rgba(15,23,42,0.24)",
          marginBottom: "1rem",
        }}
      >
        <h1 style={{ marginBottom: "0.35rem", marginTop: 0, letterSpacing: "-0.02em" }}>프로젝트 보드</h1>
        <p style={{ marginTop: 0, marginBottom: 0, color: "#bfdbfe" }}>
          3개 프로젝트를 나란히 모니터링하고 상태 변화를 즉시 확인합니다.
        </p>
      </header>

      <p style={{ marginTop: 0, color: "#334155" }}>
        템플릿명 3개를 지정하면 상태/최근 실행을 한 화면에서 병렬로 확인합니다.
      </p>

      <div
        style={{
          background: "rgba(255,255,255,0.85)",
          border: "1px solid rgba(15,23,42,0.08)",
          borderRadius: 16,
          padding: "1rem",
          marginBottom: "1rem",
          boxShadow: "0 12px 24px rgba(15,23,42,0.08)",
        }}
      >
        <form method="get" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <input
            name="templates"
            defaultValue={selected.join(",")}
            placeholder="template1,template2,template3"
            style={{
              padding: "0.6rem 0.75rem",
              minWidth: 420,
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              background: "#fff",
            }}
          />
          <button
            type="submit"
            style={{
              padding: "0.6rem 0.85rem",
              borderRadius: 10,
              border: 0,
              background: "#0f172a",
              color: "#fff",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            적용
          </button>
        </form>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1rem" }}>
        {boards.map((board) => (
          <section
            key={board.templateName}
            style={{
              background: "rgba(255,255,255,0.92)",
              border: "1px solid rgba(15,23,42,0.08)",
              borderRadius: 18,
              padding: "1rem",
              boxShadow: "0 12px 30px rgba(15,23,42,0.1)",
            }}
          >
            <h2 style={{ marginTop: 0, marginBottom: "0.25rem", fontSize: "1rem" }}>
              <code style={{ color: "#0f172a", background: "#e2e8f0", padding: "0.2rem 0.4rem", borderRadius: 8 }}>
                {board.templateName}
              </code>
            </h2>
            <div
              style={{
                color: "#0f172a",
                marginBottom: "0.75rem",
                fontWeight: 700,
                display: "inline-block",
                background: "#dbeafe",
                padding: "0.25rem 0.5rem",
                borderRadius: 999,
              }}
            >
              총 실행 {board.total}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0,1fr))",
                gap: "0.45rem",
                marginBottom: "0.75rem",
              }}
            >
              <div style={{ background: "#f8fafc", borderRadius: 10, padding: "0.45rem" }}>queued <strong>{board.queued}</strong></div>
              <div style={{ background: "#eff6ff", borderRadius: 10, padding: "0.45rem" }}>started <strong>{board.started}</strong></div>
              <div style={{ background: "#fefce8", borderRadius: 10, padding: "0.45rem" }}>retry <strong>{board.retry}</strong></div>
              <div style={{ background: "#f0fdf4", borderRadius: 10, padding: "0.45rem" }}>success <strong>{board.success}</strong></div>
              <div style={{ background: "#fef2f2", borderRadius: 10, padding: "0.45rem" }}>failure <strong>{board.failure}</strong></div>
            </div>

            <div style={{ borderTop: "1px dashed #cbd5e1", paddingTop: "0.75rem" }}>
              <strong style={{ color: "#334155" }}>최근 실행</strong>
              <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
                {board.recent.map((r) => (
                  <li key={r.run_id} style={{ marginBottom: "0.5rem", background: "#f8fafc", borderRadius: 10, padding: "0.45rem" }}>
                    <Link href={`/tasks/${r.task_id}?run_id=${r.run_id}`} style={{ textDecoration: "none", color: "#0f172a" }}>
                      <span
                        style={{
                          display: "inline-block",
                          minWidth: 62,
                          textAlign: "center",
                          borderRadius: 999,
                          padding: "0.1rem 0.35rem",
                          marginRight: "0.35rem",
                          fontWeight: 700,
                          background: r.status === "failure" ? "#fee2e2" : r.status === "success" ? "#dcfce7" : "#dbeafe",
                        }}
                      >
                        {r.status}
                      </span>
                      <span style={{ marginRight: "0.35rem", color: "#475569" }}>{r.template_version ?? "-"}</span>
                      <span style={{ color: "#64748b", fontSize: "0.84rem" }}>{r.started_at}</span>
                    </Link>
                  </li>
                ))}
                {board.recent.length === 0 ? <li style={{ color: "#6b7280" }}>최근 실행 없음</li> : null}
              </ul>
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
