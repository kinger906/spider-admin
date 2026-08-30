"""杏吧版块列表爬虫（多 fid 共用实现）。"""

from __future__ import annotations

import os
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta
from spiders.xingba_forums import XINGBA_FORUMS, XingbaForum


class XingbaForumCrawler(BaseCrawler):
    """按「最后发表」倒序抓取版块帖子：标题、发表时间、下载链接。"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    HASH_RE = re.compile(r"\b([A-Fa-f0-9]{40})\b")
    MAGNET_RE = re.compile(r"magnet:\?[^\s\"'<>]+", re.I)
    ED2K_RE = re.compile(r"ed2k://[^\s\"'<>]+", re.I)
    CLOUD_RE = re.compile(
        r"https?://[^\s\"'<>]*(?:pan\.baidu|baidu\.com/s/|aliyundrive|alipan|"
        r"quark\.cn|123pan|lanzou|ctfile|cowtransfer|pikpak|uc\.cn)[^\s\"'<>]*",
        re.I,
    )
    PUBLISHED_RE = re.compile(
        r"(?:发表于\s*)?(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)"
    )
    SKIP_TITLE_RE = re.compile(r"(公告|版规|置顶说明)")

    forum: XingbaForum

    def crawl(self) -> list[dict]:
        cfg = self.meta.config
        self._apply_page_env_overrides(cfg)

        base = str(cfg.get("base_url") or "https://www.tixanshiyanzhi.pro").rstrip("/")
        start_page = int(cfg.get("start_page") or 1)
        if cfg.get("end_page") is not None:
            end_page = int(cfg["end_page"])
        elif cfg.get("page_count") is not None:
            end_page = start_page + int(cfg["page_count"]) - 1
        else:
            end_page = start_page + int(cfg.get("max_pages") or 6) - 1
        if end_page < start_page:
            raise RuntimeError(f"end_page({end_page}) < start_page({start_page})")
        page_delay = float(cfg.get("page_delay") or 1.5)
        detail_delay = float(cfg.get("detail_delay") or 0.8)

        session = requests.Session()
        session.headers.update(self.HEADERS)
        session.headers["Referer"] = f"{base}/"

        persist = getattr(self, "persist_batch", None)
        records: list[dict] = []
        seen: set[str] = set()
        fetched_total = 0
        self._incremental_fetched = 0

        forum_name = self.forum.name
        fid = self.forum.fid

        for page in range(start_page, end_page + 1):
            self.wait_if_paused()
            if self.should_stop:
                break

            list_url = self._list_url(base, page)
            self.logger.info(
                f"[{forum_name} fid={fid}] list page {page}/{end_page}: {list_url}"
            )
            soup = self._get_soup(session, list_url)
            threads = self._parse_list(soup, base)
            if not threads:
                self.logger.info("No more threads on this page")
                break

            page_records: list[dict] = []
            for item in threads:
                self.wait_if_paused()
                if self.should_stop:
                    break

                tid = item["thread_id"]
                if tid in seen:
                    continue
                seen.add(tid)

                detail = self._fetch_detail(session, item["url"])
                published_at = detail.get("published_at") or item.get("published_at") or ""
                page_records.append(
                    {
                        "data": {
                            "thread_id": tid,
                            "forum_id": fid,
                            "forum_name": forum_name,
                            "title": item["title"],
                            "category": item.get("category") or "",
                            "published_at": published_at,
                            "download_links": detail.get("download_links") or [],
                        },
                        "url": item["url"],
                    }
                )
                time.sleep(detail_delay)

            fetched_total += len(page_records)
            self._incremental_fetched = fetched_total

            if persist and page_records:
                saved = persist(page_records)
                self.logger.info(
                    f"Page {page}: {len(page_records)} fetched, {saved} new saved"
                )
            else:
                records.extend(page_records)
                self.logger.info(f"Page {page}: {len(page_records)} fetched")

            if page < end_page:
                time.sleep(page_delay)

        self.logger.info(f"[{forum_name}] fetched {fetched_total} threads total")
        return records

    @staticmethod
    def _apply_page_env_overrides(cfg: dict) -> None:
        start = os.environ.get("XINGBA_START_PAGE") or os.environ.get("START_PAGE")
        end = os.environ.get("XINGBA_END_PAGE") or os.environ.get("END_PAGE")
        count = os.environ.get("XINGBA_PAGE_COUNT")
        if start:
            cfg["start_page"] = int(start)
        if end:
            cfg["end_page"] = int(end)
        if count:
            cfg["page_count"] = int(count)

    def _list_url(self, base: str, page: int) -> str:
        path = self.forum.list_path
        url = f"{base}{path if path.startswith('/') else '/' + path}"
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}page={page}"

    def _get_soup(self, session: requests.Session, url: str) -> BeautifulSoup:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = session.get(url, timeout=40)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                return BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                last_err = e
                self.logger.warning(f"GET failed ({attempt + 1}/3) {url}: {e}")
                time.sleep(1.5 + attempt)
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    def _canonical_thread_url(self, base: str, thread_id: str) -> str:
        return f"{base.rstrip('/')}/thread-{thread_id}-1-1.html"

    def _parse_list(self, soup: BeautifulSoup, base: str) -> list[dict]:
        items: list[dict] = []
        for tbody in soup.select("tbody[id^=normalthread_]"):
            tid = (tbody.get("id") or "").replace("normalthread_", "")
            title_a = tbody.select_one("a.xst")
            if not tid or not title_a:
                continue

            title = title_a.get_text(strip=True)
            if not title or self.SKIP_TITLE_RE.search(title):
                continue

            url = self._canonical_thread_url(base, tid)

            cat_el = tbody.select_one("th em a") or tbody.select_one("em a")
            category = cat_el.get_text(strip=True).strip("[]") if cat_el else ""

            items.append(
                {
                    "thread_id": tid,
                    "title": title,
                    "category": category,
                    "published_at": self._parse_list_published_at(tbody),
                    "url": url,
                }
            )
        return items

    def _parse_list_published_at(self, tbody) -> str:
        by_cols = tbody.select("td.by")
        if not by_cols:
            return ""
        author_col = by_cols[0]
        span = (
            author_col.select_one("span[title]")
            or author_col.select_one("em span")
            or author_col.select_one("span")
        )
        if span:
            title = (span.get("title") or "").strip()
            if title:
                return title
            text = span.get_text(strip=True)
            if text:
                return text
        em = author_col.select_one("em")
        if em:
            return em.get_text(strip=True)
        return ""

    def _parse_detail_published_at(self, soup: BeautifulSoup) -> str:
        em = soup.select_one("em[id^=authorposton]")
        if em:
            span = em.select_one("span[title]")
            if span and (span.get("title") or "").strip():
                return span.get("title").strip()
            text = em.get_text(" ", strip=True)
            m = self.PUBLISHED_RE.search(text)
            if m:
                return m.group(1)
        postlist = soup.select_one("#postlist")
        blob = postlist.get_text(" ", strip=True) if postlist else soup.get_text(" ", strip=True)
        m = self.PUBLISHED_RE.search(blob)
        return m.group(1) if m else ""

    def _fetch_detail(self, session: requests.Session, thread_url: str) -> dict:
        try:
            soup = self._get_soup(session, thread_url)
        except Exception as e:
            self.logger.warning(f"Detail failed {thread_url}: {e}")
            return {"download_links": [], "published_at": ""}

        bodies = soup.select("#postlist .t_f") or soup.select(".t_f")
        texts: list[str] = []
        hrefs: list[str] = []
        for body in bodies[:3]:
            texts.append(body.get_text("\n", strip=True))
            for a in body.select("a[href]"):
                href = (a.get("href") or "").strip()
                if href:
                    hrefs.append(urljoin(thread_url, href))

        blob = "\n".join(texts) if texts else soup.get_text("\n", strip=True)
        return {
            "download_links": self._extract_links(blob, hrefs),
            "published_at": self._parse_detail_published_at(soup),
        }

    def _extract_links(self, text: str, hrefs: list[str]) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        def add(link: str):
            link = link.strip().rstrip(".,;，。）)]}")
            if not link or link in seen:
                return
            if not self._is_download_candidate(link):
                return
            seen.add(link)
            found.append(link)

        for m in self.MAGNET_RE.findall(text):
            add(m)
        for m in self.ED2K_RE.findall(text):
            add(m)
        for m in self.CLOUD_RE.findall(text):
            add(m)
        for href in hrefs:
            add(href)
        for h in self.HASH_RE.findall(text):
            add(f"magnet:?xt=urn:btih:{h.upper()}")
        return found

    def _is_download_candidate(self, link: str) -> bool:
        low = link.lower()
        if low.startswith("javascript:") or low.startswith("#"):
            return False
        if low.startswith("magnet:") or low.startswith("ed2k:"):
            return True
        if any(
            k in low
            for k in (
                "pan.baidu",
                "baidu.com/s/",
                "aliyundrive",
                "alipan",
                "quark.cn",
                "123pan",
                "lanzou",
                "ctfile",
                "cowtransfer",
                "pikpak",
            )
        ):
            return True
        if any(
            x in low
            for x in (
                "dasp.php",
                "member.php",
                "misc.php",
                "home.php",
                "forum.php?mod=forumdisplay",
                "forum.php?mod=viewthread",
                "thread-",
                "space-uid",
                "address.zip",
                "preview",
                ".gif",
                ".jpg",
                ".png",
                ".jpeg",
                ".webp",
            )
        ):
            return False
        if "forum.php?mod=attachment" in low and "nothumb=yes" in low:
            return False
        if urlparse(link).path.lower().endswith(".torrent"):
            return True
        return False


def _make_crawler_class(forum: XingbaForum) -> type[XingbaForumCrawler]:
    def _factory(f: XingbaForum = forum) -> type[XingbaForumCrawler]:
        class _Crawler(XingbaForumCrawler):
            forum = f
            meta = CrawlerMeta(
                name=f.name,
                slug=f.slug,
                description=f"按最后发表倒序爬取{f.name}(fid={f.fid})",
                schedule="0 */4 * * *",
                config={
                    "retry_limit": 2,
                    "fid": f.fid,
                    "start_page": 1,
                    "end_page": 6,
                    "page_delay": 1.5,
                    "detail_delay": 0.8,
                    "base_url": "https://www.tixanshiyanzhi.pro",
                },
            )

        _Crawler.__name__ = f"XingbaForum{f.fid}Crawler"
        return _Crawler

    return _factory()


for _forum in XINGBA_FORUMS:
    CrawlerRegistry.register(_make_crawler_class(_forum))
