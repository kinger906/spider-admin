#!/usr/bin/env python3
"""杏吧存量回填：按 DB 游标每次爬一批页面，成功后推进游标。

用法:
  python run_xingba_backfill.py
  python run_xingba_backfill.py --start 3 --end 32
  python run_xingba_backfill.py --reset-cursor 3

环境变量（可选，覆盖参数）:
  XINGBA_START_PAGE / XINGBA_END_PAGE
  XINGBA_BATCH_SIZE / XINGBA_BACKFILL_END
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from framework import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("xingba.backfill")

SLUG = "xingba-forum-798"
DEFAULT_NEXT = 3
DEFAULT_END = 1000
DEFAULT_BATCH = 30


def main():
    parser = argparse.ArgumentParser(description="Xingba forum backfill with DB cursor")
    parser.add_argument("--start", type=int, help="Override start page for this run")
    parser.add_argument("--end", type=int, help="Override end page for this run")
    parser.add_argument("--batch-size", type=int, help="Pages per run when using cursor")
    parser.add_argument("--backfill-end", type=int, help="Final page of backfill (default 1000)")
    parser.add_argument("--reset-cursor", type=int, metavar="PAGE", help="Set backfill_next_page and exit")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--dry-run", action="store_true", help="Print planned range only")
    args = parser.parse_args()

    CrawlerRegistry.discover()
    crawler_cls = CrawlerRegistry.get(SLUG)
    if not crawler_cls:
        raise SystemExit(f"Crawler not registered: {SLUG}")

    # Ensure row exists and merge defaults without wiping cursor
    db.register_crawler(
        name=crawler_cls.meta.name,
        slug=crawler_cls.meta.slug,
        description=crawler_cls.meta.description,
        file_path=f"crawlers/spiders/{crawler_cls.meta.slug}.py",
        schedule=crawler_cls.meta.schedule,
        config=crawler_cls.meta.config,
    )

    row = db.get_crawler_by_slug(SLUG)
    cfg = dict(row["config"] if row else {})

    if args.reset_cursor is not None:
        updated = db.patch_crawler_config(SLUG, {"backfill_next_page": args.reset_cursor})
        print(f"Cursor reset: backfill_next_page={updated.get('backfill_next_page')}")
        return

    backfill_end = int(
        args.backfill_end
        or os.environ.get("XINGBA_BACKFILL_END")
        or cfg.get("backfill_end_page")
        or DEFAULT_END
    )
    batch_size = int(
        args.batch_size
        or os.environ.get("XINGBA_BATCH_SIZE")
        or cfg.get("backfill_batch_size")
        or DEFAULT_BATCH
    )
    next_page = int(cfg.get("backfill_next_page") or DEFAULT_NEXT)

    env_start = os.environ.get("XINGBA_START_PAGE") or os.environ.get("START_PAGE")
    env_end = os.environ.get("XINGBA_END_PAGE") or os.environ.get("END_PAGE")

    if args.start is not None or env_start:
        start_page = int(args.start if args.start is not None else env_start)
    else:
        start_page = next_page

    if args.end is not None or env_end:
        end_page = int(args.end if args.end is not None else env_end)
    else:
        end_page = min(start_page + batch_size - 1, backfill_end)

    if start_page > backfill_end:
        print(f"Backfill complete: next_page={start_page} > end={backfill_end}")
        return

    if end_page < start_page:
        raise SystemExit(f"Invalid range: {start_page}-{end_page}")

    print(f"Backfill plan: pages {start_page}-{end_page} (cursor={next_page}, final={backfill_end}, batch={batch_size})")
    if args.dry_run:
        return

    # Clear env so crawl() uses config_overrides, not stale shell env from a previous override
    for key in ("XINGBA_START_PAGE", "XINGBA_END_PAGE", "START_PAGE", "END_PAGE"):
        os.environ.pop(key, None)

    result = run_crawler(
        crawler_cls,
        triggered_by=args.trigger,
        config_overrides={"start_page": start_page, "end_page": end_page},
    )
    print(f"Result: {result}")

    if result.get("status") != "success":
        sys.exit(1)

    # Only advance cursor when this run followed the cursor (not a manual arbitrary range
    # that starts elsewhere). Always advance when start==cursor.
    if start_page == next_page:
        new_next = end_page + 1
        db.patch_crawler_config(
            SLUG,
            {
                "backfill_next_page": new_next,
                "backfill_end_page": backfill_end,
                "backfill_batch_size": batch_size,
                "backfill_last_success_end": end_page,
            },
        )
        print(f"Cursor advanced: backfill_next_page={new_next}")
    else:
        print(f"Cursor unchanged (manual range start={start_page}, cursor={next_page})")


if __name__ == "__main__":
    main()
