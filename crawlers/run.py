#!/usr/bin/env python3
"""CLI entry point: python run.py <crawler-slug> [--trigger schedule|manual]"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from framework import CrawlerRegistry, run_crawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main():
    parser = argparse.ArgumentParser(description="Run a registered crawler")
    parser.add_argument("crawler", nargs="?", help="Crawler slug to run")
    parser.add_argument("--trigger", default="manual", choices=["manual", "schedule", "ci"])
    parser.add_argument("--list", action="store_true", help="List all registered crawlers")
    parser.add_argument("--sync", action="store_true", help="Sync crawler registry to database")
    args = parser.parse_args()

    CrawlerRegistry.discover()

    if args.list:
        for slug, cls in CrawlerRegistry.all().items():
            print(f"  {slug:24s} {cls.meta.name} - {cls.meta.description}")
        return

    if args.sync:
        CrawlerRegistry.sync_to_db()
        print(f"Synced {len(CrawlerRegistry.all())} crawlers to database")
        return

    if not args.crawler:
        parser.print_help()
        sys.exit(1)

    crawler_cls = CrawlerRegistry.get(args.crawler)
    if not crawler_cls:
        print(f"Unknown crawler: {args.crawler}")
        print("Available crawlers:")
        for slug in CrawlerRegistry.all():
            print(f"  - {slug}")
        sys.exit(1)

    result = run_crawler(crawler_cls, triggered_by=args.trigger)
    print(f"Result: {result}")
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
