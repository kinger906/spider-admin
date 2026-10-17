#!/usr/bin/env python3
"""杏吧 SPA 连续回填（range=all）。

按 DB 游标翻页；Search API 限制 limit*page 过大（约 10000），
因此在安全页深触顶后，用 create_time 上界开新时间窗并重置 page=1。

用法：
  python run_xingba_spa_continuous.py --reset-cursor
  python run_xingba_spa_continuous.py --budget-minutes 330 --chunk-pages 40
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from framework import db
from spiders.xingba_spa_client import max_safe_page

SLUG = "xingba-spa-798"
CURSOR_KEY = "spa_backfill_next_page"
BEFORE_KEY = "spa_backfill_before_ts"
DEFAULT_MAX_PAGE = 30000
DEFAULT_CHUNK = 40
DEFAULT_BUDGET_MIN = 330  # leave headroom under GH Actions 360m timeout
DEFAULT_PAGE_SIZE = 16
START_PAGE = 1


def _next_page_from_config(config: dict | None) -> int:
    raw = (config or {}).get(CURSOR_KEY)
    if raw is None or raw == "":
        return START_PAGE
    try:
        return max(START_PAGE, int(raw))
    except (TypeError, ValueError):
        return START_PAGE


def _before_ts_from_config(config: dict | None) -> int | None:
    raw = (config or {}).get(BEFORE_KEY)
    if raw in (None, "", 0, "0"):
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _oldest_create_time_from_db(crawler_id: int) -> int | None:
    """从已入库记录取最小 create_time，供游标已超深时翻窗。"""
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT MIN((data->>'create_time')::bigint)
            FROM spider_data_records
            WHERE crawler_id = %s
              AND COALESCE(data->>'create_time', '') ~ '^[0-9]+$'
            """,
            (crawler_id,),
        )
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Xingba SPA continuous backfill (range=all)")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--max-page", type=int, default=DEFAULT_MAX_PAGE)
    parser.add_argument("--chunk-pages", type=int, default=DEFAULT_CHUNK)
    parser.add_argument("--budget-minutes", type=float, default=DEFAULT_BUDGET_MIN)
    parser.add_argument(
        "--reset-cursor",
        action="store_true",
        help="Reset page cursor and time window before starting",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    max_page = int(os.environ.get("XINGBA_SPA_CONTINUOUS_MAX") or args.max_page)
    chunk = int(os.environ.get("XINGBA_SPA_CONTINUOUS_CHUNK") or args.chunk_pages)
    budget_min = float(
        os.environ.get("XINGBA_SPA_CONTINUOUS_BUDGET_MIN") or args.budget_minutes
    )
    reset = args.reset_cursor or os.environ.get("XINGBA_SPA_RESET_CURSOR", "").lower() in (
        "1",
        "true",
        "yes",
    )

    CrawlerRegistry.discover()
    crawler_cls = CrawlerRegistry.get(SLUG)
    if not crawler_cls:
        print(f"Missing crawler: {SLUG}")
        sys.exit(1)

    page_size = int(
        (crawler_cls.meta.config or {}).get("page_size") or DEFAULT_PAGE_SIZE
    )
    safe_page = max_safe_page(page_size)

    if reset:
        db.patch_crawler_config(
            SLUG,
            {
                CURSOR_KEY: START_PAGE,
                BEFORE_KEY: None,
                "spa_range_days": "all",
            },
        )
        print(f"Cursor reset: {CURSOR_KEY}={START_PAGE}, {BEFORE_KEY}=None")

    row = db.get_crawler_by_slug(SLUG)
    cfg = row["config"] if row else {}
    next_page = _next_page_from_config(cfg)
    before_ts = _before_ts_from_config(cfg)

    # 已越过 API 深度：先按已入库最旧时间翻窗
    if next_page > safe_page:
        oldest = _oldest_create_time_from_db(row["id"]) if row else None
        if oldest and (before_ts is None or oldest < before_ts):
            before_ts = oldest
            next_page = START_PAGE
            db.patch_crawler_config(
                SLUG,
                {CURSOR_KEY: START_PAGE, BEFORE_KEY: before_ts, "spa_range_days": "all"},
            )
            print(
                f"Rolled time window from DB: {BEFORE_KEY}={before_ts}, "
                f"{CURSOR_KEY}={START_PAGE} (safe_page={safe_page})"
            )
        else:
            print(
                f"DONE: cursor={next_page} > safe_page={safe_page} "
                f"and no older create_time to roll"
            )
            return

    if next_page > max_page:
        print(f"DONE: cursor={next_page} > max={max_page}")
        return

    deadline = time.monotonic() + max(60.0, budget_min * 60.0)
    total_new = 0
    rounds = 0

    print(
        f"Continuous plan: {SLUG} from page {next_page}, max={max_page}, "
        f"safe_page={safe_page}, chunk={chunk}, budget={budget_min}m, "
        f"range=all, before_ts={before_ts}"
    )
    if args.dry_run:
        return

    while next_page <= max_page:
        remaining = deadline - time.monotonic()
        if remaining <= 30:
            print(f"Budget nearly exhausted; stop at cursor={next_page}")
            break

        # 单轮不要跨过 API 安全页深（limit*page 上限）
        end_page = min(next_page + chunk - 1, max_page, safe_page)
        if end_page < next_page:
            print(
                f"cursor={next_page} exceeds safe_page={safe_page}; "
                "expected a time-window roll earlier"
            )
            break
        rounds += 1
        print(
            f"\n=== round {rounds}: pages {next_page}-{end_page} "
            f"before_ts={before_ts} (remain≈{int(remaining)}s) ==="
        )

        overrides: dict = {
            "start_page": next_page,
            "end_page": end_page,
            "page_count": end_page - next_page + 1,
            "range_days": "all",
            "time_budget_sec": max(30, int(remaining - 20)),
        }
        if before_ts is not None:
            overrides["create_time_lt"] = before_ts

        result = run_crawler(
            crawler_cls,
            triggered_by=args.trigger,
            config_overrides=overrides,
        )
        print(f"Result: {result}")
        if result.get("status") != "success":
            # keep cursor at next_page for retry
            sys.exit(1)

        total_new += int(result.get("items") or 0)
        last_page = result.get("last_page")
        exhausted = bool(result.get("exhausted"))
        stopped_by_budget = bool(result.get("stopped_by_budget"))
        offset_capped = bool(result.get("offset_capped"))
        oldest_ts = result.get("oldest_create_time")

        if isinstance(last_page, int) and last_page >= next_page:
            new_cursor = last_page + 1
        else:
            new_cursor = next_page

        # 触顶：用本窗最旧 create_time 开下一窗，page 回 1
        if offset_capped or new_cursor > safe_page:
            roll_ts = int(oldest_ts) if oldest_ts else None
            if roll_ts and (before_ts is None or roll_ts < before_ts):
                before_ts = roll_ts
                new_cursor = START_PAGE
                print(
                    f"Time-window roll: {BEFORE_KEY}={before_ts}, "
                    f"{CURSOR_KEY}={new_cursor}"
                )
            elif exhausted:
                print("Offset capped and list exhausted; done.")
                db.patch_crawler_config(
                    SLUG,
                    {
                        CURSOR_KEY: new_cursor,
                        BEFORE_KEY: before_ts,
                        "spa_backfill_max_page": max_page,
                        "spa_range_days": "all",
                        "spa_continuous_last_run_at": int(time.time()),
                    },
                )
                break
            else:
                print(
                    f"Cannot roll further (oldest={oldest_ts}, before={before_ts}); stop"
                )
                db.patch_crawler_config(
                    SLUG,
                    {
                        CURSOR_KEY: new_cursor,
                        BEFORE_KEY: before_ts,
                        "spa_continuous_last_run_at": int(time.time()),
                    },
                )
                break

        db.patch_crawler_config(
            SLUG,
            {
                CURSOR_KEY: new_cursor,
                BEFORE_KEY: before_ts,
                "spa_backfill_max_page": max_page,
                "spa_range_days": "all",
                "spa_continuous_last_run_at": int(time.time()),
            },
        )
        print(
            f"Cursor updated: {CURSOR_KEY}={new_cursor}, {BEFORE_KEY}={before_ts}"
        )

        if exhausted:
            if before_ts is not None:
                # 当前时间窗空了 = 没有更旧的帖
                print(f"Reached end of time window before_ts={before_ts}; done.")
            else:
                print(f"Reached end of list at page {last_page}; done.")
            break
        if new_cursor > max_page:
            print(f"Reached max_page={max_page}; done.")
            break
        if stopped_by_budget or time.monotonic() >= deadline:
            print(f"Time budget stop; resume later from page {new_cursor}")
            break

        next_page = new_cursor

    final = db.get_crawler_by_slug(SLUG)
    fcfg = final["config"] if final else {}
    print(
        f"\nDone rounds={rounds}, new_records={total_new}, "
        f"cursor={_next_page_from_config(fcfg)}, before_ts={_before_ts_from_config(fcfg)}"
    )


if __name__ == "__main__":
    main()
