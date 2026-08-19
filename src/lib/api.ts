"use server";

import { db } from "~/db";
import { crawlers, tasks, dataRecords, mediaFiles, systemLogs } from "~/db/schema";
import { eq, desc, sql, and, like, gte, lte, count } from "drizzle-orm";

// ─── Crawlers ───

export async function getCrawlers() {
  return db.select().from(crawlers).orderBy(desc(crawlers.updatedAt));
}

export async function getCrawler(id: number) {
  const rows = await db.select().from(crawlers).where(eq(crawlers.id, id)).limit(1);
  return rows[0] ?? null;
}

export async function updateCrawler(id: number, data: { enabled?: boolean; schedule?: string; config?: Record<string, unknown>; retryLimit?: number }) {
  await db.update(crawlers).set({ ...data, updatedAt: new Date() }).where(eq(crawlers.id, id));
}

export async function deleteCrawler(id: number) {
  await db.delete(crawlers).where(eq(crawlers.id, id));
}

// ─── Tasks ───

export async function getTasks(crawlerId?: number, page = 1, pageSize = 20) {
  const conditions = crawlerId ? eq(tasks.crawlerId, crawlerId) : undefined;
  const offset = (page - 1) * pageSize;

  const [rows, total] = await Promise.all([
    db.select().from(tasks).where(conditions).orderBy(desc(tasks.createdAt)).limit(pageSize).offset(offset),
    db.select({ count: count() }).from(tasks).where(conditions),
  ]);

  return { data: rows, total: total[0]?.count ?? 0, page, pageSize };
}

export async function getTask(id: number) {
  const rows = await db.select().from(tasks).where(eq(tasks.id, id)).limit(1);
  return rows[0] ?? null;
}

// ─── Data Records ───

export async function getDataRecords(crawlerId?: number, search?: string, page = 1, pageSize = 50) {
  const conditions = [];
  if (crawlerId) conditions.push(eq(dataRecords.crawlerId, crawlerId));
  if (search) conditions.push(sql`${dataRecords.data}::text ILIKE ${"%" + search + "%"}`);

  const where = conditions.length > 0 ? and(...conditions) : undefined;
  const offset = (page - 1) * pageSize;

  const [rows, total] = await Promise.all([
    db.select().from(dataRecords).where(where).orderBy(desc(dataRecords.createdAt)).limit(pageSize).offset(offset),
    db.select({ count: count() }).from(dataRecords).where(where),
  ]);

  return { data: rows, total: total[0]?.count ?? 0, page, pageSize };
}

// ─── Media Files ───

export async function getMediaFiles(crawlerId?: number, page = 1, pageSize = 50) {
  const where = crawlerId ? eq(mediaFiles.crawlerId, crawlerId) : undefined;
  const offset = (page - 1) * pageSize;

  const rows = await db.select().from(mediaFiles).where(where).orderBy(desc(mediaFiles.createdAt)).limit(pageSize).offset(offset);
  return rows;
}

// ─── System Logs ───

export async function getSystemLogs(level?: string, source?: string, page = 1, pageSize = 100) {
  const conditions = [];
  if (level) conditions.push(eq(systemLogs.level, level));
  if (source) conditions.push(eq(systemLogs.source, source));

  const where = conditions.length > 0 ? and(...conditions) : undefined;
  const offset = (page - 1) * pageSize;

  const rows = await db.select().from(systemLogs).where(where).orderBy(desc(systemLogs.createdAt)).limit(pageSize).offset(offset);
  return rows;
}

// ─── Dashboard Stats ───

export async function getDashboardStats() {
  const [crawlerRows, taskRows, recordRows, recentTasks] = await Promise.all([
    db.select({
      total: count(),
      running: sql<number>`count(*) filter (where ${crawlers.status} = 'running')`,
      error: sql<number>`count(*) filter (where ${crawlers.status} = 'error')`,
    }).from(crawlers),
    db.select({
      total: count(),
      success: sql<number>`count(*) filter (where ${tasks.status} = 'success')`,
      failed: sql<number>`count(*) filter (where ${tasks.status} = 'failed')`,
    }).from(tasks),
    db.select({ total: count() }).from(dataRecords),
    db.select().from(tasks).orderBy(desc(tasks.createdAt)).limit(10),
  ]);

  return {
    crawlers: crawlerRows[0],
    tasks: taskRows[0],
    records: recordRows[0],
    recentTasks,
  };
}

// ─── Crawler API Endpoint (for Python crawlers to call) ───

export async function triggerCrawler(id: number) {
  await db.update(crawlers).set({ status: "running", lastRunAt: new Date(), updatedAt: new Date() }).where(eq(crawlers.id, id));
  return { success: true };
}

export async function pauseCrawler(id: number) {
  await db.update(crawlers).set({ status: "paused", updatedAt: new Date() }).where(eq(crawlers.id, id));
}

export async function stopCrawler(id: number) {
  await db.update(crawlers).set({ status: "idle", updatedAt: new Date() }).where(eq(crawlers.id, id));
}
