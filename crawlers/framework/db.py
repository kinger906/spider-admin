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
