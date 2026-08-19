"""Auto-discovery and registration of crawler modules."""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from .base import BaseCrawler
from . import db


class CrawlerRegistry:
    _crawlers: dict[str, type[BaseCrawler]] = {}

    @classmethod
    def register(cls, crawler_cls: type[BaseCrawler]):
        slug = crawler_cls.meta.slug
        cls._crawlers[slug] = crawler_cls
        return crawler_cls

    @classmethod
    def get(cls, slug: str) -> type[BaseCrawler] | None:
        return cls._crawlers.get(slug)

    @classmethod
    def all(cls) -> dict[str, type[BaseCrawler]]:
        return dict(cls._crawlers)

    @classmethod
    def discover(cls, directory: str | None = None):
        """Scan the spiders/ directory and import all modules to trigger registration."""
        if directory is None:
            directory = str(Path(__file__).parent.parent / "spiders")

        if not os.path.isdir(directory):
            return

        for fname in sorted(os.listdir(directory)):
            if fname.startswith("_") or not fname.endswith(".py"):
                continue
            module_name = f"spiders.{fname[:-3]}"
            fpath = os.path.join(directory, fname)
            spec = importlib.util.spec_from_file_location(module_name, fpath)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

    @classmethod
    def sync_to_db(cls):
        """Register all discovered crawlers into the database."""
        for slug, crawler_cls in cls._crawlers.items():
            meta = crawler_cls.meta
            db.register_crawler(
                name=meta.name,
                slug=meta.slug,
                description=meta.description,
                file_path=f"crawlers/spiders/{meta.slug}.py",
                schedule=meta.schedule,
                config=meta.config,
            )
