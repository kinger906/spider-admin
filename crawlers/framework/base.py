"""Base crawler class that all crawlers must extend."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import time

logger = logging.getLogger("crawler")


@dataclass
class CrawlerMeta:
    name: str
    slug: str
    description: str = ""
    schedule: str | None = None
    config: dict = field(default_factory=dict)


class BaseCrawler(ABC):
    meta: CrawlerMeta

    def __init__(self):
        self._should_stop = False
        self._paused = False
        self.logger = logging.getLogger(f"crawler.{self.meta.slug}")

    @abstractmethod
    def crawl(self) -> list[dict]:
        """Execute the crawl and return a list of record dicts.
        Each dict should have at minimum a 'data' key with the payload,
        and optionally a 'url' key."""
        ...

    def on_start(self):
        """Hook called before crawl begins."""
        pass

    def on_finish(self, records: list[dict]):
        """Hook called after crawl completes."""
        pass

    def on_error(self, error: Exception):
        """Hook called when crawl fails."""
        pass

    def request_stop(self):
        self._should_stop = True

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def wait_if_paused(self):
        while self._paused and not self._should_stop:
            time.sleep(1)

    @property
    def should_stop(self) -> bool:
        return self._should_stop
