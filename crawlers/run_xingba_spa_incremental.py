#!/usr/bin/env python3
"""杏吧 SPA 日常增量：新主题+半年范围，最新 N 页（默认 6）。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler

SLUG = "xingba-spa-798"
DEFAULT_PAGES = 6


def main():
    parser = argparse.ArgumentParser(description="Xingba SPA incremental crawl")
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES, help="Latest pages")
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    args = parser.parse_args()

    pages = int(os.environ.get("XINGBA_SPA_INCREMENTAL_PAGES") or args.pages)
    CrawlerRegistry.discover()

    crawler_cls = CrawlerRegistry.get(SLUG)
    if not crawler_cls:
        print(f"Missing crawler: {SLUG}")
        sys.exit(1)

    print(f"\n=== {crawler_cls.meta.name} ({SLUG}) pages 1-{pages} ===")
    result = run_crawler(
        crawler_cls,
        triggered_by=args.trigger,
        config_overrides={"start_page": 1, "end_page": pages},
    )
    print(f"Result: {result}")
    if result.get("status") != "success":
        sys.exit(1)

    print(f"\nDone. new_records={result.get('items') or 0}")


if __name__ == "__main__":
    main()
