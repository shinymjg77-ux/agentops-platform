import { redirect } from "next/navigation";

export async function POST(
  _request: Request,
  context: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await context.params;
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/tasks/${taskId}/retry`, {
    method: "POST",
    cache: "no-store",
  });
  redirect(`/tasks/${taskId}`);
}
