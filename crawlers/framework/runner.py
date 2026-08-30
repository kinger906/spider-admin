"""Task runner with retry logic, logging, and DB persistence."""

import io
import logging
import sys
import traceback

from .base import BaseCrawler
from . import db
from .registry import crawler_file_path

logger = logging.getLogger("crawler.runner")
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def _attach_crawler_logging(log_stream: io.StringIO) -> list[logging.Handler]:
    """Mirror crawler logs to stdout (CI console) and an in-memory buffer (DB)."""
    formatter = logging.Formatter(_LOG_FORMAT)
    handlers: list[logging.Handler] = []

    for stream in (log_stream, sys.stdout):
        h = logging.StreamHandler(stream)
        h.setFormatter(formatter)
        handlers.append(h)

    crawler_logger = logging.getLogger("crawler")
    crawler_logger.setLevel(logging.INFO)
    crawler_logger.propagate = False
    for h in handlers:
        crawler_logger.addHandler(h)
    return handlers


def _detach_crawler_logging(handlers: list[logging.Handler]) -> None:
    crawler_logger = logging.getLogger("crawler")
    for h in handlers:
        crawler_logger.removeHandler(h)


def run_crawler(
    crawler_cls: type[BaseCrawler],
    triggered_by: str = "manual",
    config_overrides: dict | None = None,
) -> dict:
    meta = crawler_cls.meta
    if config_overrides:
        meta.config.update(config_overrides)

    log_stream = io.StringIO()
    handlers = _attach_crawler_logging(log_stream)

    crawler_id = db.register_crawler(
        name=meta.name,
        slug=meta.slug,
        description=meta.description,
        file_path=crawler_file_path(meta.slug),
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
            instance._incremental_saved = 0

            def _persist(batch: list[dict]) -> int:
                n = db.save_records_dedup(crawler_id, task_id, batch)
                instance._incremental_saved += n
                return n

            instance.persist_batch = _persist  # type: ignore[attr-defined]
            instance.on_start()
            logger.info(f"[{meta.slug}] Crawl attempt {attempt + 1}")

            records = instance.crawl()
            leftover = db.save_records_dedup(crawler_id, task_id, records) if records else 0
            new_count = int(getattr(instance, "_incremental_saved", 0)) + leftover
            instance.on_finish(records)

            db.finish_task(task_id, crawler_id, "success", new_count, logs=log_stream.getvalue())
            db.save_log(
                "info",
                meta.slug,
                f"Task {task_id} succeeded: {new_count} new / fetched={len(records) + getattr(instance, '_incremental_fetched', 0)}",
            )

            _detach_crawler_logging(handlers)
            return {
                "status": "success",
                "task_id": task_id,
                "items": new_count,
                "total_fetched": getattr(instance, "_incremental_fetched", None) or len(records),
            }
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

    _detach_crawler_logging(handlers)
    return {"status": "failed", "task_id": task_id, "error": str(last_error)}
