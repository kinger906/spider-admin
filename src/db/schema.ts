import {
  pgTable,
  text,
  timestamp,
  integer,
  jsonb,
  boolean,
  serial,
  varchar,
  pgEnum,
} from "drizzle-orm/pg-core";

export const crawlerStatusEnum = pgEnum("spider_crawler_status", [
  "idle",
  "running",
  "paused",
  "error",
  "disabled",
]);

export const taskStatusEnum = pgEnum("spider_task_status", [
  "pending",
  "running",
  "success",
  "failed",
  "cancelled",
]);

export const crawlers = pgTable("spider_crawlers", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 128 }).notNull().unique(),
  slug: varchar("slug", { length: 128 }).notNull().unique(),
  description: text("description"),
  filePath: varchar("file_path", { length: 512 }).notNull(),
  status: crawlerStatusEnum("status").notNull().default("idle"),
  schedule: varchar("schedule", { length: 64 }),
  config: jsonb("config").$type<Record<string, unknown>>().default({}),
  retryLimit: integer("retry_limit").notNull().default(3),
  enabled: boolean("enabled").notNull().default(true),
  lastRunAt: timestamp("last_run_at"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
});

export const tasks = pgTable("spider_tasks", {
  id: serial("id").primaryKey(),
  crawlerId: integer("crawler_id")
    .notNull()
    .references(() => crawlers.id, { onDelete: "cascade" }),
  status: taskStatusEnum("status").notNull().default("pending"),
  triggeredBy: varchar("triggered_by", { length: 32 }).notNull().default("manual"),
  startedAt: timestamp("started_at"),
  finishedAt: timestamp("finished_at"),
  itemsCount: integer("items_count").notNull().default(0),
  errorMessage: text("error_message"),
  retryCount: integer("retry_count").notNull().default(0),
  logs: text("logs"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const dataRecords = pgTable("spider_data_records", {
  id: serial("id").primaryKey(),
  crawlerId: integer("crawler_id")
    .notNull()
    .references(() => crawlers.id, { onDelete: "cascade" }),
  taskId: integer("task_id").references(() => tasks.id, { onDelete: "set null" }),
  data: jsonb("data").$type<Record<string, unknown>>().notNull(),
  url: text("url"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const mediaFiles = pgTable("spider_media_files", {
  id: serial("id").primaryKey(),
  crawlerId: integer("crawler_id")
    .notNull()
    .references(() => crawlers.id, { onDelete: "cascade" }),
  taskId: integer("task_id").references(() => tasks.id, { onDelete: "set null" }),
  fileName: varchar("file_name", { length: 512 }).notNull(),
  blobUrl: text("blob_url").notNull(),
  mimeType: varchar("mime_type", { length: 128 }),
  sizeBytes: integer("size_bytes"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const systemLogs = pgTable("spider_system_logs", {
  id: serial("id").primaryKey(),
  level: varchar("level", { length: 16 }).notNull().default("info"),
  source: varchar("source", { length: 128 }),
  message: text("message").notNull(),
  meta: jsonb("meta").$type<Record<string, unknown>>(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
