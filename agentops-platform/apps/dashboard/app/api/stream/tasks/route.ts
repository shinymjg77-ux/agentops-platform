export async function GET() {
  const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${baseUrl}/v1/stream/tasks`, {
    cache: "no-store",
    headers: {
      Accept: "text/event-stream",
    },
  });

  if (!upstream.ok || !upstream.body) {
    return new Response("upstream unavailable", { status: 502 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
