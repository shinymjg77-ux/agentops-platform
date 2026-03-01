import { redirect } from "next/navigation";

export async function POST(_request: Request, context: { params: Promise<{ policyId: string }> }) {
  const { policyId } = await context.params;
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  await fetch(`${baseUrl}/v1/policies/${policyId}/enable`, { method: "POST", cache: "no-store" });
  redirect("/policies");
}
