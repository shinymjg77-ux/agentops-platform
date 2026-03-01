import Link from "next/link";
import LiveTaskStream from "./components/live-task-stream";

type TaskItem = {
  task_id: string;
  template_name: string;
  template_version?: string;
  status: string;
  created_at: string;
  celery_task_id: string;
};

async function getTasks(): Promise<TaskItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/tasks?limit=10`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  return (await res.json()) as TaskItem[];
}

function statusColor(status: string): string {
  if (status === "success") return "#166534";
  if (status === "failure") return "#991b1b";
  if (status === "started" || status === "running") return "#1d4ed8";
  return "#374151";
}

export default async function HomePage() {
  const tasks = await getTasks();
  return (
    <main style={{ maxWidth: 980, margin: "0 auto" }}>
      <LiveTaskStream />
      <h1 style={{ marginBottom: "0.5rem" }}>AgentOps Dashboard</h1>
      <p style={{ marginTop: 0, color: "#374151" }}>작업 상태 모니터링 초기 화면</p>
      <div style={{ margin: "1rem 0", padding: "1rem", background: "#ffffff", borderRadius: 12 }}>
        <strong>현재 작업 수:</strong> {tasks.length}
      </div>
      <div style={{ overflowX: "auto", background: "#fff", borderRadius: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.75rem" }}>템플릿</th>
              <th style={{ padding: "0.75rem" }}>버전</th>
              <th style={{ padding: "0.75rem" }}>상태</th>
              <th style={{ padding: "0.75rem" }}>생성시각(UTC)</th>
              <th style={{ padding: "0.75rem" }}>Task ID</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.task_id} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "0.75rem" }}>{task.template_name}</td>
                <td style={{ padding: "0.75rem" }}>{task.template_version ?? "-"}</td>
                <td style={{ padding: "0.75rem", color: statusColor(task.status), fontWeight: 600 }}>
                  {task.status}
                </td>
                <td style={{ padding: "0.75rem" }}>{task.created_at}</td>
                <td style={{ padding: "0.75rem" }}>
                  <div>
                    <code>{task.celery_task_id}</code>
                  </div>
                  <div style={{ marginTop: "0.25rem" }}>
                    <Link href={`/tasks/${task.task_id}`} style={{ fontSize: "0.875rem" }}>
                      상세 보기
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: "1rem", color: "#6b7280" }}>
                  표시할 작업이 없습니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  );
}
