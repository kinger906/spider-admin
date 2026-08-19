"""GitHub Trending repositories crawler."""

import requests
from bs4 import BeautifulSoup
from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta


class GithubTrendingCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="GitHub Trending",
        slug="github-trending",
        description="Crawls GitHub Trending page for popular repositories",
        schedule="0 8 * * *",
    )

    def crawl(self) -> list[dict]:
        resp = requests.get("https://github.com/trending", timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        records = []

        for article in soup.select("article.Box-row"):
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            repo_path = h2.get("href", "").strip("/")
            desc_el = article.select_one("p")
            lang_el = article.select_one("[itemprop='programmingLanguage']")
            stars_el = article.select("a.Link--muted")

            records.append({
                "data": {
                    "repo": repo_path,
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                    "language": lang_el.get_text(strip=True) if lang_el else "",
                    "stars_today": stars_el[-1].get_text(strip=True) if stars_el else "",
                },
                "url": f"https://github.com/{repo_path}",
            })

            self.wait_if_paused()
            if self.should_stop:
                break

        return records


CrawlerRegistry.register(GithubTrendingCrawler)
