import Link from "next/link";
import LiveTaskStream from "../../components/live-task-stream";

type TaskDetail = {
  task_id: string;
  template_name: string;
  template_version?: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
  run: {
    run_id: string;
    celery_task_id: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    result: Record<string, unknown> | null;
    template_version?: string;
    adapter_version?: string | null;
    error_code?: string | null;
    error_message?: string | null;
  };
};

type TaskLog = {
  run_id: string;
  ts: string;
  level: string;
  message: string;
  metadata: Record<string, unknown> | null;
};

type RunItem = {
  run_id: string;
  celery_task_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  result: Record<string, unknown> | null;
  template_version?: string | null;
  adapter_version?: string | null;
  error_code?: string | null;
  error_message?: string | null;
};

function buildTaskDetailHref(
  taskId: string,
  params: { runId?: string; compareRunId?: string; failedOnly?: boolean },
): string {
  const query = new URLSearchParams();
  if (params.runId) query.set("run_id", params.runId);
  if (params.compareRunId) query.set("compare_run_id", params.compareRunId);
  if (params.failedOnly) query.set("failed_only", "1");
  const qs = query.toString();
  return qs ? `/tasks/${taskId}?${qs}` : `/tasks/${taskId}`;
}

async function getTaskDetail(taskId: string): Promise<TaskDetail | null> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/tasks/${taskId}`, { cache: "no-store" });
  if (!res.ok) {
    return null;
  }
  return (await res.json()) as TaskDetail;
}

async function getTaskRuns(taskId: string): Promise<RunItem[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const res = await fetch(`${baseUrl}/v1/tasks/${taskId}/runs?limit=50`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  return (await res.json()) as RunItem[];
}

async function getTaskLogs(taskId: string, runId?: string): Promise<TaskLog[]> {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const query = runId ? `?limit=200&run_id=${encodeURIComponent(runId)}` : "?limit=200";
  const res = await fetch(`${baseUrl}/v1/tasks/${taskId}/logs${query}`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  return (await res.json()) as TaskLog[];
}

export default async function TaskDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ taskId: string }>;
  searchParams: Promise<{ run_id?: string; compare_run_id?: string; failed_only?: string }>;
}) {
  const { taskId } = await params;
  const { run_id: requestedRunId, compare_run_id: requestedCompareRunId, failed_only: failedOnlyRaw } =
    await searchParams;
  const failedOnly = failedOnlyRaw === "1";
  const [task, runs] = await Promise.all([getTaskDetail(taskId), getTaskRuns(taskId)]);
  const visibleRuns = failedOnly ? runs.filter((run) => run.status === "failure") : runs;
  const selectedRunId = requestedRunId ?? visibleRuns[0]?.run_id ?? runs[0]?.run_id;
  const selectedRun = runs.find((run) => run.run_id === selectedRunId);
  const compareRunId =
    requestedCompareRunId && requestedCompareRunId !== selectedRunId ? requestedCompareRunId : undefined;
  const compareRun = runs.find((run) => run.run_id === compareRunId);
  const logs = await getTaskLogs(taskId, selectedRunId);

  if (!task) {
    return (
      <main style={{ maxWidth: 980, margin: "0 auto" }}>
        <h1>작업 상세</h1>
        <p>작업을 찾을 수 없습니다.</p>
        <Link href="/">목록으로</Link>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 980, margin: "0 auto" }}>
      <LiveTaskStream />
      <h1 style={{ marginBottom: "0.5rem" }}>작업 상세</h1>
      <p style={{ marginTop: 0, color: "#4b5563" }}>{task.task_id}</p>

      <div style={{ background: "#ffffff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <div><strong>템플릿:</strong> {task.template_name}</div>
        <div><strong>템플릿 버전:</strong> {task.template_version ?? task.run.template_version ?? "-"}</div>
        <div><strong>상태:</strong> {task.status}</div>
        <div><strong>생성시각:</strong> {task.created_at}</div>
        <div><strong>실행 ID:</strong> {task.run.run_id}</div>
        <div><strong>Celery ID:</strong> {task.run.celery_task_id}</div>
        <div><strong>시작:</strong> {task.run.started_at}</div>
        <div><strong>종료:</strong> {task.run.finished_at ?? "-"}</div>
        <form action={`/tasks/${task.task_id}/retry`} method="post" style={{ marginTop: "0.75rem" }}>
          <button
            type="submit"
            style={{
              background: "#111827",
              color: "#fff",
              border: 0,
              borderRadius: 8,
              padding: "0.5rem 0.75rem",
              cursor: "pointer",
            }}
          >
            이 작업 재시도
          </button>
        </form>
      </div>

      <div style={{ background: "#ffffff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>실행 이력</h2>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.75rem" }}>
          <Link
            href={buildTaskDetailHref(taskId, {
              runId: selectedRunId,
              compareRunId: compareRunId,
              failedOnly: !failedOnly,
            })}
          >
            {failedOnly ? "전체 실행 보기" : "실패 실행만 보기"}
          </Link>
          <span style={{ color: "#6b7280", fontSize: "0.875rem" }}>
            표시 {visibleRuns.length} / 전체 {runs.length}
          </span>
        </div>
        {visibleRuns.length === 0 ? (
          <p style={{ color: "#6b7280" }}>실행 이력이 없습니다.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {visibleRuns.map((run) => (
              <li key={run.run_id} style={{ padding: "0.5rem 0", borderTop: "1px solid #e5e7eb" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
                  <Link
                    href={buildTaskDetailHref(taskId, {
                      runId: run.run_id,
                      failedOnly,
                    })}
                    style={{ fontWeight: run.run_id === selectedRunId ? 700 : 400 }}
                  >
                    {run.run_id.slice(0, 8)}... | {run.status} | {run.started_at}
                  </Link>
                  {selectedRunId && run.run_id !== selectedRunId ? (
                    <Link
                      href={buildTaskDetailHref(taskId, {
                        runId: selectedRunId,
                        compareRunId: run.run_id,
                        failedOnly,
                      })}
                      style={{ fontSize: "0.875rem" }}
                    >
                      이 실행과 비교
                    </Link>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selectedRun && compareRun ? (
        <div style={{ background: "#ffffff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>실행 결과 비교</h2>
          <p style={{ marginTop: 0, color: "#4b5563" }}>
            기준: <code>{selectedRun.run_id}</code> / 비교: <code>{compareRun.run_id}</code>
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "0.75rem" }}>
              <div>
                <strong>기준 상태:</strong> {selectedRun.status}
              </div>
              <div>
                <strong>시작:</strong> {selectedRun.started_at}
              </div>
              <div>
                <strong>종료:</strong> {selectedRun.finished_at ?? "-"}
              </div>
              <div>
                <strong>어댑터 버전:</strong> {selectedRun.adapter_version ?? "-"}
              </div>
              <div>
                <strong>오류:</strong> {selectedRun.error_code ?? "-"}
              </div>
              <pre style={{ marginTop: "0.5rem", background: "#f8fafc", padding: "0.5rem", overflowX: "auto" }}>
                {JSON.stringify(selectedRun.result, null, 2)}
              </pre>
            </div>
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "0.75rem" }}>
              <div>
                <strong>비교 상태:</strong> {compareRun.status}
              </div>
              <div>
                <strong>시작:</strong> {compareRun.started_at}
              </div>
              <div>
                <strong>종료:</strong> {compareRun.finished_at ?? "-"}
              </div>
              <div>
                <strong>어댑터 버전:</strong> {compareRun.adapter_version ?? "-"}
              </div>
              <div>
                <strong>오류:</strong> {compareRun.error_code ?? "-"}
              </div>
              <pre style={{ marginTop: "0.5rem", background: "#f8fafc", padding: "0.5rem", overflowX: "auto" }}>
                {JSON.stringify(compareRun.result, null, 2)}
              </pre>
            </div>
          </div>
          <div style={{ marginTop: "0.75rem" }}>
            <Link
              href={buildTaskDetailHref(taskId, {
                runId: selectedRunId,
                failedOnly,
              })}
              style={{ fontSize: "0.875rem" }}
            >
              비교 해제
            </Link>
          </div>
        </div>
      ) : null}

      <div style={{ background: "#ffffff", borderRadius: 12, padding: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>실행 로그</h2>
        {selectedRunId ? (
          <p style={{ marginTop: 0, color: "#4b5563" }}>
            선택 실행 ID: <code>{selectedRunId}</code>
          </p>
        ) : null}
        {logs.length === 0 ? (
          <p style={{ color: "#6b7280" }}>로그가 없습니다.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", background: "#f8fafc" }}>
                <th style={{ padding: "0.5rem" }}>시각</th>
                <th style={{ padding: "0.5rem" }}>레벨</th>
                <th style={{ padding: "0.5rem" }}>메시지</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, idx) => (
                <tr key={`${log.ts}-${idx}`} style={{ borderTop: "1px solid #e5e7eb" }}>
                  <td style={{ padding: "0.5rem", whiteSpace: "nowrap" }}>{log.ts}</td>
                  <td style={{ padding: "0.5rem" }}>{log.level}</td>
                  <td style={{ padding: "0.5rem" }}>
                    <div>{log.message}</div>
                    {log.metadata ? (
                      <pre style={{ margin: "0.25rem 0 0", background: "#f8fafc", padding: "0.5rem", overflowX: "auto" }}>
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Link href="/">목록으로</Link>
    </main>
  );
}
