"""Task runner with retry logic, logging, and DB persistence."""

import logging
import traceback
import io
from .base import BaseCrawler
from . import db

logger = logging.getLogger("crawler.runner")


def run_crawler(
    crawler_cls: type[BaseCrawler],
    triggered_by: str = "manual",
) -> dict:
    meta = crawler_cls.meta
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger("crawler").addHandler(handler)

    crawler_id = db.register_crawler(
        name=meta.name,
        slug=meta.slug,
        description=meta.description,
        file_path=f"crawlers/spiders/{meta.slug}.py",
        schedule=meta.schedule,
        config=meta.config,
    )
    task_id = db.create_task(crawler_id, triggered_by)
    db.save_log("info", meta.slug, f"Task {task_id} started", {"triggered_by": triggered_by})

    retry_limit = meta.config.get("retry_limit", 3)
    attempt = 0
    last_error = None

    while attempt <= retry_limit:
        try:
            instance = crawler_cls()
            instance.on_start()
            logger.info(f"[{meta.slug}] Crawl attempt {attempt + 1}")

            records = instance.crawl()
            new_count = db.save_records_dedup(crawler_id, task_id, records)
            instance.on_finish(records)

            db.finish_task(task_id, crawler_id, "success", new_count, logs=log_stream.getvalue())
            db.save_log("info", meta.slug, f"Task {task_id} succeeded: {new_count} new / {len(records)} total")

            logging.getLogger("crawler").removeHandler(handler)
            return {"status": "success", "task_id": task_id, "items": new_count, "total_fetched": len(records)}
        except Exception as e:
            last_error = e
            attempt += 1
            logger.error(f"[{meta.slug}] Attempt {attempt} failed: {e}")
            try:
                instance.on_error(e)
            except Exception:
                pass

            if attempt > retry_limit:
                break

    error_msg = f"{last_error}\n{traceback.format_exc()}"
    db.finish_task(task_id, crawler_id, "failed", error_message=error_msg, logs=log_stream.getvalue())
    db.save_log("error", meta.slug, f"Task {task_id} failed after {attempt} attempts", {"error": str(last_error)})

    logging.getLogger("crawler").removeHandler(handler)
    return {"status": "failed", "task_id": task_id, "error": str(last_error)}
