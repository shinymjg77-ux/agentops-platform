import { redirect } from "next/navigation";

export async function POST(
  request: Request,
  context: { params: Promise<{ templateId: string }> },
) {
  const { templateId } = await context.params;
  const formData = await request.formData();

  const version = String(formData.get("version") ?? "").trim();
  const adapterName = String(formData.get("adapter_name") ?? "").trim();
  const adapterVersionRaw = String(formData.get("adapter_version") ?? "").trim();
  const inputSchemaRaw = String(formData.get("input_schema") ?? "").trim();
  const setDefault = String(formData.get("set_default") ?? "") === "1";

  if (!version || !adapterName) {
    redirect(`/templates/${templateId}`);
  }

  let inputSchema: Record<string, unknown> = { type: "object", properties: {} };
  if (inputSchemaRaw.length > 0) {
    try {
      inputSchema = JSON.parse(inputSchemaRaw) as Record<string, unknown>;
    } catch {
      inputSchema = { type: "object", properties: {} };
    }
  }

  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/template-registry/${templateId}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      version,
      adapter_name: adapterName,
      adapter_version: adapterVersionRaw.length > 0 ? adapterVersionRaw : null,
      input_schema: inputSchema,
      set_default: setDefault,
    }),
  });

  redirect(`/templates/${templateId}`);
}
