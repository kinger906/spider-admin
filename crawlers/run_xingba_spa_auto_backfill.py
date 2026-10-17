#!/usr/bin/env python3
"""杏吧 SPA 自动回填：按 DB 游标推进，每次 6 页，直到 max_page。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from framework import db

SLUG = "xingba-spa-798"
CURSOR_KEY = "spa_backfill_next_page"
DEFAULT_PAGES = 6
DEFAULT_MAX_PAGE = 1000
START_PAGE = 1


def _next_page_from_config(config: dict | None) -> int:
    raw = (config or {}).get(CURSOR_KEY)
    if raw is None or raw == "":
        return START_PAGE
    try:
        return max(START_PAGE, int(raw))
    except (TypeError, ValueError):
        return START_PAGE


def main():
    parser = argparse.ArgumentParser(description="Xingba SPA auto backfill with DB cursor")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    parser.add_argument("--max-page", type=int, default=DEFAULT_MAX_PAGE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pages_per_run = int(os.environ.get("XINGBA_SPA_AUTO_BACKFILL_PAGES") or args.pages)
    max_page = int(os.environ.get("XINGBA_SPA_AUTO_BACKFILL_MAX") or args.max_page)
    CrawlerRegistry.discover()

    crawler_cls = CrawlerRegistry.get(SLUG)
    if not crawler_cls:
        print(f"Missing crawler: {SLUG}")
        sys.exit(1)

    row = db.get_crawler_by_slug(SLUG)
    next_page = _next_page_from_config(row["config"] if row else None)

    if next_page > max_page:
        print(f"DONE {crawler_cls.meta.name}: cursor={next_page} > max={max_page}")
        return

    end_page = min(next_page + pages_per_run - 1, max_page)
    print(
        f"\n=== {crawler_cls.meta.name} ({SLUG}) "
        f"pages {next_page}-{end_page} (cursor→{end_page + 1}) ==="
    )

    if args.dry_run:
        return

    result = run_crawler(
        crawler_cls,
        triggered_by=args.trigger,
        config_overrides={
            "start_page": next_page,
            "end_page": end_page,
            "page_count": end_page - next_page + 1,
        },
    )
    print(f"Result: {result}")
    if result.get("status") != "success":
        sys.exit(1)

    new_cursor = end_page + 1
    db.patch_crawler_config(
        SLUG,
        {
            CURSOR_KEY: new_cursor,
            "spa_backfill_max_page": max_page,
            "spa_backfill_pages_per_run": pages_per_run,
        },
    )
    print(f"Cursor updated: {CURSOR_KEY}={new_cursor}")
    print(f"\nDone. new_records={result.get('items') or 0}")


if __name__ == "__main__":
    main()
