import { redirect } from "next/navigation";

export async function POST(request: Request) {
  const form = await request.formData();
  const body = {
    name: String(form.get("name") ?? "").trim(),
    scope_type: String(form.get("scope_type") ?? "template").trim(),
    scope_ref: String(form.get("scope_ref") ?? "").trim() || null,
    metric_key: String(form.get("metric_key") ?? "failure_rate").trim(),
    operator: String(form.get("operator") ?? "gte").trim(),
    threshold_value: Number(String(form.get("threshold_value") ?? "0")),
    window_minutes: Number(String(form.get("window_minutes") ?? "15")),
    cooldown_minutes: Number(String(form.get("cooldown_minutes") ?? "30")),
    action_type: String(form.get("action_type") ?? "pause_schedule").trim(),
  };

  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  redirect("/policies");
}
