import os
import psycopg2
from psycopg2.extras import execute_values, Json
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()


@contextmanager
def get_connection():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def register_crawler(name: str, slug: str, description: str, file_path: str, schedule: str | None = None, config: dict | None = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO spider_crawlers (name, slug, description, file_path, schedule, config)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                file_path = EXCLUDED.file_path,
                schedule = EXCLUDED.schedule,
                -- 代码默认配置覆盖同名字段，但保留 DB 中已有的扩展键（如 backfill 游标）
                config = COALESCE(spider_crawlers.config, '{}'::jsonb) || EXCLUDED.config,
                updated_at = NOW()
            RETURNING id
            """,
            (name, slug, description, file_path, schedule, Json(config or {})),
        )
        return cur.fetchone()[0]


def get_crawler_by_slug(slug: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, slug, config FROM spider_crawlers WHERE slug = %s",
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "slug": row[2], "config": row[3] or {}}


def patch_crawler_config(slug: str, patch: dict) -> dict:
    """Merge patch into crawler config JSON and return the new config."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE spider_crawlers
            SET config = COALESCE(config, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE slug = %s
            RETURNING config
            """,
            (Json(patch), slug),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Crawler not found: {slug}")
        return row[0] or {}



def create_task(crawler_id: int, triggered_by: str = "manual") -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO spider_tasks (crawler_id, triggered_by, status, started_at) VALUES (%s, %s, 'running', NOW()) RETURNING id",
            (crawler_id, triggered_by),
        )
        task_id = cur.fetchone()[0]
        cur.execute("UPDATE spider_crawlers SET status = 'running', last_run_at = NOW() WHERE id = %s", (crawler_id,))
        return task_id


def finish_task(task_id: int, crawler_id: int, status: str, items_count: int = 0, error_message: str | None = None, logs: str | None = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE spider_tasks SET status = %s, finished_at = NOW(), items_count = %s, error_message = %s, logs = %s WHERE id = %s",
            (status, items_count, error_message, logs, task_id),
        )
        cur.execute("UPDATE spider_crawlers SET status = 'idle' WHERE id = %s", (crawler_id,))


def save_records(crawler_id: int, task_id: int, records: list[dict]):
    if not records:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        values = [(crawler_id, task_id, Json(r.get("data", r)), r.get("url")) for r in records]
        execute_values(
            cur,
            "INSERT INTO spider_data_records (crawler_id, task_id, data, url) VALUES %s",
            values,
            template="(%s, %s, %s, %s)",
        )


def save_log(level: str, source: str, message: str, meta: dict | None = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO spider_system_logs (level, source, message, meta) VALUES (%s, %s, %s, %s)",
            (level, source, message, Json(meta) if meta else None),
        )


def check_url_exists(crawler_id: int, url: str) -> bool:
    """Check if a URL already exists for this crawler (dedup)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM spider_data_records WHERE crawler_id = %s AND url = %s LIMIT 1",
            (crawler_id, url),
        )
        return cur.fetchone() is not None


def _record_exists(cur, crawler_id: int, data: dict, url: str | None) -> bool:
    """Dedup by data.thread_id when present, else by url."""
    thread_id = data.get("thread_id")
    if thread_id is not None and str(thread_id).strip():
        cur.execute(
            """
            SELECT 1 FROM spider_data_records
            WHERE crawler_id = %s AND data->>'thread_id' = %s
            LIMIT 1
            """,
            (crawler_id, str(thread_id)),
        )
        if cur.fetchone():
            return True
        return False
    if url:
        cur.execute(
            "SELECT 1 FROM spider_data_records WHERE crawler_id = %s AND url = %s LIMIT 1",
            (crawler_id, url),
        )
        return cur.fetchone() is not None
    return False


def save_records_dedup(crawler_id: int, task_id: int, records: list[dict]) -> int:
    """Save records with deduplication (thread_id preferred, else url)."""
    if not records:
        return 0
    with get_connection() as conn:
        cur = conn.cursor()
        new_count = 0
        for r in records:
            data = r.get("data", r)
            url = r.get("url")
            if _record_exists(cur, crawler_id, data if isinstance(data, dict) else {}, url):
                continue
            cur.execute(
                "INSERT INTO spider_data_records (crawler_id, task_id, data, url) VALUES (%s, %s, %s, %s)",
                (crawler_id, task_id, Json(data), url),
            )
            new_count += 1
        return new_count


XINGBA_SPA_POSTS_DDL = """
CREATE TABLE IF NOT EXISTS spider_xingba_spa_posts (
  id SERIAL PRIMARY KEY,
  crawler_id INTEGER REFERENCES spider_crawlers(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES spider_tasks(id) ON DELETE SET NULL,
  post_id VARCHAR(64) NOT NULL,
  eid BIGINT,
  category_id VARCHAR(64) NOT NULL DEFAULT '798',
  forum_name VARCHAR(128),
  title TEXT NOT NULL DEFAULT '',
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  published_at TIMESTAMP,
  create_time BIGINT,
  status INTEGER,
  user_id VARCHAR(64),
  attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
  download_links JSONB NOT NULL DEFAULT '[]'::jsonb,
  text_preview TEXT,
  url TEXT,
  source_page INTEGER,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (category_id, post_id)
);
CREATE INDEX IF NOT EXISTS idx_xingba_spa_posts_published
  ON spider_xingba_spa_posts (published_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_xingba_spa_posts_create_time
  ON spider_xingba_spa_posts (create_time DESC NULLS LAST);
"""


def ensure_xingba_spa_posts_table() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(XINGBA_SPA_POSTS_DDL)


def save_xingba_spa_posts(
    crawler_id: int | None,
    task_id: int | None,
    rows: list[dict],
) -> int:
    """Upsert SPA posts into spider_xingba_spa_posts. Returns newly inserted count."""
    if not rows:
        return 0
    ensure_xingba_spa_posts_table()
    new_count = 0
    with get_connection() as conn:
        cur = conn.cursor()
        for row in rows:
            post_id = str(row.get("post_id") or "").strip()
            if not post_id:
                continue
            category_id = str(row.get("category_id") or "798")
            published_at = row.get("published_at") or None
            cur.execute(
                """
                INSERT INTO spider_xingba_spa_posts (
                  crawler_id, task_id, post_id, eid, category_id, forum_name,
                  title, tags, published_at, create_time, status, user_id,
                  attachments, download_links, text_preview, url, source_page, raw
                ) VALUES (
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (category_id, post_id) DO UPDATE SET
                  crawler_id = COALESCE(EXCLUDED.crawler_id, spider_xingba_spa_posts.crawler_id),
                  task_id = COALESCE(EXCLUDED.task_id, spider_xingba_spa_posts.task_id),
                  eid = COALESCE(EXCLUDED.eid, spider_xingba_spa_posts.eid),
                  forum_name = EXCLUDED.forum_name,
                  title = EXCLUDED.title,
                  tags = EXCLUDED.tags,
                  published_at = COALESCE(EXCLUDED.published_at, spider_xingba_spa_posts.published_at),
                  create_time = COALESCE(EXCLUDED.create_time, spider_xingba_spa_posts.create_time),
                  status = COALESCE(EXCLUDED.status, spider_xingba_spa_posts.status),
                  user_id = COALESCE(EXCLUDED.user_id, spider_xingba_spa_posts.user_id),
                  attachments = EXCLUDED.attachments,
                  download_links = EXCLUDED.download_links,
                  text_preview = EXCLUDED.text_preview,
                  url = COALESCE(EXCLUDED.url, spider_xingba_spa_posts.url),
                  source_page = COALESCE(EXCLUDED.source_page, spider_xingba_spa_posts.source_page),
                  raw = EXCLUDED.raw,
                  updated_at = NOW()
                RETURNING (xmax = 0) AS inserted
                """,
                (
                    crawler_id,
                    task_id,
                    post_id,
                    row.get("eid"),
                    category_id,
                    row.get("forum_name"),
                    row.get("title") or "",
                    Json(row.get("tags") or []),
                    published_at if published_at else None,
                    row.get("create_time"),
                    row.get("status"),
                    row.get("user_id") or None,
                    Json(row.get("attachments") or []),
                    Json(row.get("download_links") or []),
                    row.get("text_preview"),
                    row.get("url"),
                    row.get("source_page"),
                    Json(row.get("raw") or {}),
                ),
            )
            result = cur.fetchone()
            if result and result[0]:
                new_count += 1
    return new_count
