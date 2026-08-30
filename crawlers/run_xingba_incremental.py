#!/usr/bin/env python3
"""杏吧日常增量：按顺序爬取全部版块，每类最新 N 页（默认 6）。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from spiders.xingba_forums import XINGBA_FORUMS

DEFAULT_PAGES = 6


def main():
    parser = argparse.ArgumentParser(description="Xingba incremental crawl all forums")
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES, help="Latest pages per forum")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    args = parser.parse_args()

    pages = int(os.environ.get("XINGBA_INCREMENTAL_PAGES") or args.pages)
    CrawlerRegistry.discover()

    failed: list[str] = []
    total_new = 0

    for forum in XINGBA_FORUMS:
        crawler_cls = CrawlerRegistry.get(forum.slug)
        if not crawler_cls:
            print(f"SKIP missing crawler: {forum.slug}")
            failed.append(forum.slug)
            continue

        print(f"\n=== {forum.name} ({forum.slug}) pages 1-{pages} ===")
        result = run_crawler(
            crawler_cls,
            triggered_by=args.trigger,
            config_overrides={"start_page": 1, "end_page": pages},
        )
        print(f"Result: {result}")
        if result.get("status") != "success":
            failed.append(forum.slug)
        else:
            total_new += int(result.get("items") or 0)

    print(f"\nDone. new_records={total_new}, failed={failed or 'none'}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
