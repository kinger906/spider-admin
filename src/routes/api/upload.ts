import { json } from "@solidjs/router";
import type { APIEvent } from "@solidjs/start/server";
import { put } from "@vercel/blob";
import { db } from "~/db";
import { mediaFiles } from "~/db/schema";

export async function POST(event: APIEvent) {
  const auth = event.request.headers.get("authorization");
  if (auth !== `Bearer ${process.env.API_SECRET}`) {
    return json({ error: "Unauthorized" }, { status: 401 });
  }

  const formData = await event.request.formData();
  const file = formData.get("file") as File | null;
  const crawlerId = Number(formData.get("crawler_id"));
  const taskId = formData.get("task_id") ? Number(formData.get("task_id")) : null;

  if (!file || isNaN(crawlerId)) {
    return json({ error: "file and crawler_id required" }, { status: 400 });
  }

  const blob = await put(`spider/${crawlerId}/${file.name}`, file, { access: "public" });

  await db.insert(mediaFiles).values({
    crawlerId,
    taskId,
    fileName: file.name,
    blobUrl: blob.url,
    mimeType: file.type,
    sizeBytes: file.size,
  });

  return json({ url: blob.url });
}
