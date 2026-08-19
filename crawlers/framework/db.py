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
                config = EXCLUDED.config,
                updated_at = NOW()
            RETURNING id
            """,
            (name, slug, description, file_path, schedule, Json(config or {})),
        )
        return cur.fetchone()[0]


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


def save_records_dedup(crawler_id: int, task_id: int, records: list[dict]) -> int:
    """Save records with URL-based deduplication. Returns count of new records saved."""
    if not records:
        return 0
    with get_connection() as conn:
        cur = conn.cursor()
        new_count = 0
        for r in records:
            url = r.get("url")
            if url:
                cur.execute(
                    "SELECT 1 FROM spider_data_records WHERE crawler_id = %s AND url = %s LIMIT 1",
                    (crawler_id, url),
                )
                if cur.fetchone():
                    continue
            cur.execute(
                "INSERT INTO spider_data_records (crawler_id, task_id, data, url) VALUES (%s, %s, %s, %s)",
                (crawler_id, task_id, Json(r.get("data", r)), url),
            )
            new_count += 1
        return new_count
