import { redirect } from "next/navigation";

export async function POST(
  _request: Request,
  context: { params: Promise<{ templateId: string; version: string }> },
) {
  const { templateId, version } = await context.params;
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

  await fetch(`${baseUrl}/v1/template-registry/${templateId}/versions/${encodeURIComponent(version)}/set-default`, {
    method: "POST",
    cache: "no-store",
  });

  redirect(`/templates/${templateId}`);
}
