import { redirect } from "next/navigation";

export async function POST(request: Request) {
  const formData = await request.formData();
  const name = String(formData.get("name") ?? "").trim();
  const displayName = String(formData.get("display_name") ?? "").trim();
  const descriptionRaw = String(formData.get("description") ?? "").trim();

  if (!name || !displayName) {
    redirect("/templates");
  }

  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/template-registry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      display_name: displayName,
      description: descriptionRaw.length > 0 ? descriptionRaw : null,
    }),
  });

  redirect("/templates");
}
