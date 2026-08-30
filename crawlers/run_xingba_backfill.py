#!/usr/bin/env python3
"""杏吧手动回填：指定版块 + 起始页 + 爬取页数。"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler
from spiders.xingba_forums import XINGBA_FORUMS, resolve_forum

DEFAULT_START = 1
DEFAULT_PAGE_COUNT = 100


def main():
    names = [f.name for f in XINGBA_FORUMS]
    slugs = [f.slug for f in XINGBA_FORUMS]
    parser = argparse.ArgumentParser(description="Xingba manual backfill for one forum")
    parser.add_argument(
        "--forum",
        required=False,
        choices=names,
        help="Forum display name",
    )
    parser.add_argument(
        "--slug",
        required=False,
        choices=slugs,
        help="Forum crawler slug (alternative to --forum)",
    )
    parser.add_argument("--start", type=int, default=DEFAULT_START, help="Start page")
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGE_COUNT,
        help="Number of pages to crawl",
    )
    parser.add_argument("--trigger", default="ci", choices=["manual", "schedule", "ci"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    forum_key = (
        args.forum
        or args.slug
        or os.environ.get("XINGBA_FORUM")
        or os.environ.get("XINGBA_FORUM_NAME")
        or os.environ.get("XINGBA_SLUG")
        or os.environ.get("XINGBA_FORUM_SLUG")
    )
    if not forum_key:
        raise SystemExit(f"--forum required. Choices: {', '.join(names)}")

    start_page = int(os.environ.get("XINGBA_START_PAGE") or args.start)
    page_count = int(os.environ.get("XINGBA_PAGE_COUNT") or args.pages)
    end_page = start_page + page_count - 1

    try:
        forum = resolve_forum(forum_key)
    except KeyError:
        raise SystemExit(f"Unknown forum: {forum_key}. Choices: {', '.join(names)}") from None
    slug = forum.slug

    print(
        f"Backfill plan: {forum.name} ({slug}) "
        f"pages {start_page}-{end_page} (count={page_count})"
    )
    if args.dry_run:
        return

    CrawlerRegistry.discover()
    crawler_cls = CrawlerRegistry.get(slug)
    if not crawler_cls:
        raise SystemExit(f"Crawler not registered: {slug}")

    for key in ("XINGBA_START_PAGE", "XINGBA_END_PAGE", "START_PAGE", "END_PAGE", "XINGBA_PAGE_COUNT"):
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
