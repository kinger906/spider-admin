#!/usr/bin/env python3
"""杏吧 SPA 手动回填：指定起始页 + 爬取页数。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler

SLUG = "xingba-spa-798"
DEFAULT_START = 1
DEFAULT_PAGE_COUNT = 100


def main():
    parser = argparse.ArgumentParser(description="Xingba SPA manual backfill")
    parser.add_argument("--start", type=int, default=DEFAULT_START, help="Start page")
    parser.add_argument(
        "--pages", type=int, default=DEFAULT_PAGE_COUNT, help="Number of pages"
    )
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start_page = int(os.environ.get("XINGBA_SPA_START_PAGE") or args.start)
    page_count = int(os.environ.get("XINGBA_SPA_PAGE_COUNT") or args.pages)
    end_page = start_page + page_count - 1

    print(
        f"Backfill plan: {SLUG} pages {start_page}-{end_page} (count={page_count})"
    )
    if args.dry_run:
        return

    CrawlerRegistry.discover()
    crawler_cls = CrawlerRegistry.get(SLUG)
    if not crawler_cls:
        raise SystemExit(f"Crawler not registered: {SLUG}")

    for key in (
        "XINGBA_SPA_START_PAGE",
        "XINGBA_SPA_END_PAGE",
        "XINGBA_SPA_PAGE_COUNT",
        "XINGBA_START_PAGE",
        "XINGBA_END_PAGE",
        "START_PAGE",
        "END_PAGE",
    ):
        os.environ.pop(key, None)

    result = run_crawler(
        crawler_cls,
        triggered_by=args.trigger,
        config_overrides={
            "start_page": start_page,
            "end_page": end_page,
            "page_count": page_count,
        },
    )
    print(f"Result: {result}")
    if result.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
