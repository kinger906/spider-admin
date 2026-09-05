#!/usr/bin/env python3
"""杏吧自动回填：全部版块按 DB 游标推进，每次 6 页，直到 1000 页。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from framework import db
from spiders.xingba_forums import (
    AUTO_BACKFILL_CURSOR_KEY,
    AUTO_BACKFILL_MAX_PAGE,
    AUTO_BACKFILL_PAGES_PER_RUN,
    AUTO_BACKFILL_START_PAGE,
    XINGBA_FORUMS,
)


def _next_page_from_config(config: dict | None) -> int:
    raw = (config or {}).get(AUTO_BACKFILL_CURSOR_KEY)
    if raw is None or raw == "":
        return AUTO_BACKFILL_START_PAGE
    try:
        return max(AUTO_BACKFILL_START_PAGE, int(raw))
    except (TypeError, ValueError):
        return AUTO_BACKFILL_START_PAGE


def main():
    parser = argparse.ArgumentParser(description="Xingba auto backfill with DB cursor")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument(
        "--pages",
        type=int,
        default=AUTO_BACKFILL_PAGES_PER_RUN,
        help=f"Pages per forum per run (default {AUTO_BACKFILL_PAGES_PER_RUN})",
    )
    parser.add_argument(
        "--max-page",
        type=int,
        default=AUTO_BACKFILL_MAX_PAGE,
        help=f"Stop after this page (default {AUTO_BACKFILL_MAX_PAGE})",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pages_per_run = int(os.environ.get("XINGBA_AUTO_BACKFILL_PAGES") or args.pages)
    max_page = int(os.environ.get("XINGBA_AUTO_BACKFILL_MAX") or args.max_page)
    CrawlerRegistry.discover()

    failed: list[str] = []
    skipped_done: list[str] = []
    total_new = 0

    for forum in XINGBA_FORUMS:
        crawler_cls = CrawlerRegistry.get(forum.slug)
        if not crawler_cls:
            print(f"SKIP missing crawler: {forum.slug}")
            failed.append(forum.slug)
            continue

        row = db.get_crawler_by_slug(forum.slug)
        next_page = _next_page_from_config(row["config"] if row else None)

        if next_page > max_page:
            print(f"DONE {forum.name}: cursor={next_page} > max={max_page}")
            skipped_done.append(forum.slug)
            continue

        end_page = min(next_page + pages_per_run - 1, max_page)
        print(
            f"\n=== {forum.name} ({forum.slug}) "
            f"pages {next_page}-{end_page} (cursor→{end_page + 1}) ==="
        )

        if args.dry_run:
            continue

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
            failed.append(forum.slug)
            continue

        new_cursor = end_page + 1
        db.patch_crawler_config(
            forum.slug,
            {
                AUTO_BACKFILL_CURSOR_KEY: new_cursor,
                "backfill_max_page": max_page,
                "backfill_pages_per_run": pages_per_run,
            },
        )
        print(f"Cursor updated: {forum.name} {AUTO_BACKFILL_CURSOR_KEY}={new_cursor}")
        total_new += int(result.get("items") or 0)

    print(
        f"\nDone. new_records={total_new}, "
        f"failed={failed or 'none'}, done_forums={skipped_done or 'none'}"
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
