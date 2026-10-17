#!/usr/bin/env python3
"""杏吧 SPA 连续回填（range=all）。

按 DB 游标从第 1 页往后爬，直到：
- 列表耗尽（空页）
- 达到 max_page（默认 30000，约站点全部 ~29239 页）
- 或本轮 time budget 用尽（适配 GitHub Actions 单 job 最长约 6 小时）

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

SLUG = "xingba-spa-798"
CURSOR_KEY = "spa_backfill_next_page"
DEFAULT_MAX_PAGE = 30000
DEFAULT_CHUNK = 40
DEFAULT_BUDGET_MIN = 330  # leave headroom under GH Actions 360m timeout
START_PAGE = 1


def _next_page_from_config(config: dict | None) -> int:
    raw = (config or {}).get(CURSOR_KEY)
    if raw is None or raw == "":
        return START_PAGE
    try:
        return max(START_PAGE, int(raw))
    except (TypeError, ValueError):
        return START_PAGE


def main() -> None:
    parser = argparse.ArgumentParser(description="Xingba SPA continuous backfill (range=all)")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--max-page", type=int, default=DEFAULT_MAX_PAGE)
    parser.add_argument("--chunk-pages", type=int, default=DEFAULT_CHUNK)
    parser.add_argument("--budget-minutes", type=float, default=DEFAULT_BUDGET_MIN)
    parser.add_argument(
        "--reset-cursor",
        action="store_true",
        help="Reset cursor to page 1 before starting",
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

    if reset:
        db.patch_crawler_config(SLUG, {CURSOR_KEY: START_PAGE, "spa_range_days": "all"})
        print(f"Cursor reset: {CURSOR_KEY}={START_PAGE}")

    row = db.get_crawler_by_slug(SLUG)
    next_page = _next_page_from_config(row["config"] if row else None)
    if next_page > max_page:
        print(f"DONE: cursor={next_page} > max={max_page}")
        return

    deadline = time.monotonic() + max(60.0, budget_min * 60.0)
    total_new = 0
    rounds = 0

    print(
        f"Continuous plan: {SLUG} from page {next_page}, max={max_page}, "
        f"chunk={chunk}, budget={budget_min}m, range=all"
    )
    if args.dry_run:
        return

    while next_page <= max_page:
        remaining = deadline - time.monotonic()
        if remaining <= 30:
            print(f"Budget nearly exhausted; stop at cursor={next_page}")
            break

        end_page = min(next_page + chunk - 1, max_page)
        rounds += 1
        print(
            f"\n=== round {rounds}: pages {next_page}-{end_page} "
            f"(remain≈{int(remaining)}s) ==="
        )

        result = run_crawler(
            crawler_cls,
            triggered_by=args.trigger,
            config_overrides={
                "start_page": next_page,
                "end_page": end_page,
                "page_count": end_page - next_page + 1,
                "range_days": "all",
                "time_budget_sec": max(30, int(remaining - 20)),
            },
        )
        print(f"Result: {result}")
        if result.get("status") != "success":
            # keep cursor at next_page for retry
            sys.exit(1)

        total_new += int(result.get("items") or 0)
        last_page = result.get("last_page")
        exhausted = bool(result.get("exhausted"))
        stopped_by_budget = bool(result.get("stopped_by_budget"))

        if isinstance(last_page, int) and last_page >= next_page:
            new_cursor = last_page + 1
        else:
            # no page completed in this round
            new_cursor = next_page

        db.patch_crawler_config(
            SLUG,
            {
                CURSOR_KEY: new_cursor,
                "spa_backfill_max_page": max_page,
                "spa_range_days": "all",
                "spa_continuous_last_run_at": int(time.time()),
            },
        )
        print(f"Cursor updated: {CURSOR_KEY}={new_cursor}")

        if exhausted:
            print(f"Reached end of list at page {last_page}; done.")
            break
        if new_cursor > max_page:
            print(f"Reached max_page={max_page}; done.")
            break
        if stopped_by_budget or time.monotonic() >= deadline:
            print(f"Time budget stop; resume later from page {new_cursor}")
            break

        next_page = new_cursor

    print(f"\nDone rounds={rounds}, new_records={total_new}, cursor={_next_page_from_config(db.get_crawler_by_slug(SLUG)['config'])}")


if __name__ == "__main__":
    main()
