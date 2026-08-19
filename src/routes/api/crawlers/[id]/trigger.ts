import { json } from "@solidjs/router";
import type { APIEvent } from "@solidjs/start/server";
import { db } from "~/db";
import { crawlers } from "~/db/schema";
import { eq } from "drizzle-orm";

export async function POST(event: APIEvent) {
  const auth = event.request.headers.get("authorization");
  if (auth !== `Bearer ${process.env.API_SECRET}`) {
    return json({ error: "Unauthorized" }, { status: 401 });
  }

  const id = Number(event.params.id);
  if (isNaN(id)) return json({ error: "Invalid ID" }, { status: 400 });

  await db.update(crawlers).set({ status: "running", lastRunAt: new Date(), updatedAt: new Date() }).where(eq(crawlers.id, id));
  return json({ success: true });
}
