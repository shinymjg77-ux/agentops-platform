import { redirect } from "next/navigation";

export async function POST(request: Request) {
  const form = await request.formData();
  const name = String(form.get("name") ?? "").trim();
  const templateName = String(form.get("template_name") ?? "").trim();
  const templateVersionRaw = String(form.get("template_version") ?? "").trim();
  const rruleText = String(form.get("rrule_text") ?? "every:60").trim();
  const payloadRaw = String(form.get("payload") ?? "{}").trim();

  if (!name || !templateName) {
    redirect("/schedules");
  }

  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(payloadRaw) as Record<string, unknown>;
  } catch {
    payload = {};
  }

  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      template_name: templateName,
      template_version: templateVersionRaw.length > 0 ? templateVersionRaw : null,
      payload,
      rrule_text: rruleText,
      timezone: "Asia/Seoul",
      is_active: true,
    }),
  });

  redirect("/schedules");
}
