"""Hacker News front page crawler."""

import requests
from bs4 import BeautifulSoup
from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta


class HackerNewsCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="Hacker News",
        slug="hackernews",
        description="Crawls the Hacker News front page for top stories",
        schedule="0 */6 * * *",
    )

    def crawl(self) -> list[dict]:
        resp = requests.get("https://news.ycombinator.com/", timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        records = []

        for row in soup.select("tr.athing"):
            title_el = row.select_one(".titleline > a")
            if not title_el:
                continue
            subtext = row.find_next_sibling("tr")
            score_el = subtext.select_one(".score") if subtext else None

            records.append({
                "data": {
                    "title": title_el.get_text(strip=True),
                    "link": title_el.get("href", ""),
                    "score": score_el.get_text(strip=True) if score_el else "0 points",
                    "hn_id": row.get("id", ""),
                },
                "url": title_el.get("href", ""),
            })

            self.wait_if_paused()
            if self.should_stop:
                break

        return records


CrawlerRegistry.register(HackerNewsCrawler)
