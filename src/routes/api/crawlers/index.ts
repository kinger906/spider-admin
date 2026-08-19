import { json } from "@solidjs/router";
import type { APIEvent } from "@solidjs/start/server";
import { db } from "~/db";
import { crawlers } from "~/db/schema";

function checkAuth(event: APIEvent) {
  const auth = event.request.headers.get("authorization");
  if (auth !== `Bearer ${process.env.API_SECRET}`) {
    throw json({ error: "Unauthorized" }, { status: 401 });
  }
}

export async function GET(event: APIEvent) {
  checkAuth(event);
  const rows = await db.select().from(crawlers);
  return json(rows);
}
