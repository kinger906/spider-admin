import type { APIEvent } from "@solidjs/start/server";

/** Lightweight health check — does not touch the database. */
export async function GET(_event: APIEvent) {
  return new Response(
    JSON.stringify({
      ok: true,
      hasDatabaseUrl: Boolean(process.env.DATABASE_URL),
      hasApiSecret: Boolean(process.env.API_SECRET) && (process.env.API_SECRET?.length ?? 0) >= 32,
      timestamp: new Date().toISOString(),
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" },
    }
  );
}
