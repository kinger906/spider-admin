"""杏吧新版 SPA 版块爬虫（mainPage 内部分页 API）。

目标页示例：
https://www.bin7sha1n.website/mainPage/666a736faa91b688401ae8da/132/798?filter=publish&range=all

- 排序：新主题（create_time DESC）
- 时间范围：默认全部（range=all）
- 分页：Search/Social/Query 的 page/limit（非 Discuz HTML 翻页）
- 存储：与旧爬虫相同，写入 spider_data_records
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta
from spiders.xingba_spa_client import XingbaSpaClient


class XingbaSpaForumCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="杏吧SPA华人下载区",
        slug="xingba-spa-798",
        description=(
            "新版 SPA 按新主题+全部时间爬取华人下载区(categories_id=798)，"
            "内部分页走 Search/Social/Query"
        ),
        schedule="0 */4 * * *",
        config={
            "retry_limit": 2,
            "site_base": "https://www.bin7sha1n.website",
            "realm_id": "666a736faa91b688401ae8da",
            "channel_id": "132",
            "category_id": "798",
            "forum_name": "华人性爱下载",
            "filter": "publish",
            "range_days": "all",
            "page_size": 16,
            "start_page": 1,
            "end_page": 6,
            "page_delay": 1.0,
            "sort_field": "create_time",
            "time_budget_sec": 0,
        },
    )

    MAGNET_RE = re.compile(r"magnet:\?[^\s\"'<>]+", re.I)
    ED2K_RE = re.compile(r"ed2k://[^\s\"'<>]+", re.I)
    HASH_RE = re.compile(r"\b([A-Fa-f0-9]{40})\b")
    CLOUD_RE = re.compile(
        r"https?://[^\s\"'<>]*(?:pan\.baidu|baidu\.com/s/|aliyundrive|alipan|"
        r"quark\.cn|123pan|lanzou|ctfile|cowtransfer|pikpak|uc\.cn)[^\s\"'<>]*",
        re.I,
    )

    def crawl(self) -> list[dict]:
        cfg = dict(self.meta.config)
        self._apply_env_overrides(cfg)

        start_page = int(cfg.get("start_page") or 1)
        if cfg.get("end_page") is not None:
            end_page = int(cfg["end_page"])
        elif cfg.get("page_count") is not None:
            end_page = start_page + int(cfg["page_count"]) - 1
        else:
            end_page = start_page + int(cfg.get("max_pages") or 6) - 1
        if end_page < start_page:
            raise RuntimeError(f"end_page({end_page}) < start_page({start_page})")

        page_size = int(cfg.get("page_size") or 16)
        page_delay = float(cfg.get("page_delay") or 1.0)
        range_days = cfg.get("range_days")
        range_days_i = int(range_days) if range_days not in (None, "", "all") else None
        time_budget_sec = float(cfg.get("time_budget_sec") or 0)
        deadline = (
            time.monotonic() + time_budget_sec if time_budget_sec > 0 else None
        )
        category_id = str(cfg.get("category_id") or "798")
        forum_name = str(cfg.get("forum_name") or "华人性爱下载")
        site_base = str(cfg.get("site_base") or "https://www.bin7sha1n.website").rstrip(
            "/"
        )
        realm_id = str(cfg.get("realm_id") or "666a736faa91b688401ae8da")
        channel_id = str(cfg.get("channel_id") or "132")
        sort_field = str(cfg.get("sort_field") or "create_time")

        self._last_completed_page = start_page - 1
        self._exhausted = False
        self._stopped_by_budget = False

        user_name = (
            os.environ.get("XINGBA_SPA_USER")
            or os.environ.get("XINGBA_USER")
            or str(cfg.get("user_name") or "")
        ).strip()
        password = (
            os.environ.get("XINGBA_SPA_PASS")
            or os.environ.get("XINGBA_PASS")
            or str(cfg.get("password") or "")
        ).strip()
        if not user_name or not password:
            raise RuntimeError(
                "缺少账号：请在环境变量设置 XINGBA_SPA_USER / XINGBA_SPA_PASS"
            )

        client = XingbaSpaClient(
            site_base=site_base, user_name=user_name, password=password
        )
        self.logger.info(f"SPA bootstrap login as {user_name}")
        client.bootstrap()

        persist = getattr(self, "persist_batch", None)
        seen: set[str] = set()
        fetched_total = 0
        self._incremental_fetched = 0
        records: list[dict] = []

        list_base = (
            f"{site_base}/mainPage/{realm_id}/{channel_id}/{category_id}"
            f"?filter=publish&range={range_days_i or 'all'}"
        )

        for page in range(start_page, end_page + 1):
            self.wait_if_paused()
            if self.should_stop:
                break
            if deadline is not None and time.monotonic() >= deadline:
                self._stopped_by_budget = True
                self.logger.info(
                    f"Time budget reached before page {page}; "
                    f"last_completed={self._last_completed_page}"
                )
                break

            self.logger.info(
                f"[SPA {forum_name} cat={category_id}] page {page}/{end_page} "
                f"size={page_size} range={range_days_i if range_days_i is not None else 'all'}"
            )
            result = client.query_posts(
                category_id=category_id,
                page=page,
                limit=page_size,
                range_days=range_days_i,
                sort_field=sort_field,
            )
            items = result.get("list") or []
            if not items:
                self._exhausted = True
                self.logger.info("No more posts on this page (exhausted)")
                break

            page_rows: list[dict] = []
            for item in items:
                self.wait_if_paused()
                if self.should_stop:
                    break
                post_id = str(item.get("id") or "").strip()
                if not post_id or post_id in seen:
                    continue
                seen.add(post_id)

                text_blob = self._join_text(item)
                attachments = self._normalize_attachments(item.get("attachments") or [])
                download_links = self._extract_links(text_blob)
                for att in attachments:
                    # 附件种子用稳定伪链接保存，便于后续补下载
                    h = att.get("hash") or ""
                    name = att.get("name") or ""
                    if h:
                        download_links.append(f"xingba-att://{h}/{name}".rstrip("/"))

                published_at = self._ts_to_dt(item.get("create_time"))
                title = (item.get("title") or "").strip()
                tags = item.get("tags") or []
                if not isinstance(tags, list):
                    tags = [str(tags)]
                url = f"{list_base}#post-{post_id}"

                row = {
                    "post_id": post_id,
                    "eid": item.get("eid"),
                    "category_id": category_id,
                    "forum_name": forum_name,
                    "title": title,
                    "tags": [str(t) for t in tags],
                    "published_at": published_at,
                    "create_time": item.get("create_time"),
                    "status": item.get("status"),
                    "user_id": str(item.get("user_id") or ""),
                    "attachments": attachments,
                    "download_links": download_links,
                    "text_preview": text_blob[:2000],
                    "url": url,
                    "source_page": page,
                    "raw": {
                        "type": item.get("type"),
                        "classify_id": item.get("classify_id"),
                        "trend": item.get("trend"),
                    },
                }
                page_rows.append(row)

            fetched_total += len(page_rows)
            self._incremental_fetched = fetched_total

            if page_rows:
                batch = [
                    {"data": self._record_payload(r), "url": r.get("url")}
                    for r in page_rows
                ]
                if persist:
                    saved = persist(batch)
                else:
                    records.extend(batch)
                    saved = len(batch)
                self.logger.info(
                    f"Page {page}: {len(page_rows)} fetched, {saved} new saved "
                    f"(api_count={result.get('count')})"
                )

            self._last_completed_page = page

            if page < end_page:
                time.sleep(page_delay)

        self.logger.info(
            f"[SPA {forum_name}] fetched {fetched_total} posts total "
            f"(last_page={self._last_completed_page}, exhausted={self._exhausted}, "
            f"budget_stop={self._stopped_by_budget})"
        )
        return records

    def on_start(self):
        # capture task_id if runner set it later; runner sets persist after on_start
        pass

    @staticmethod
    def _apply_env_overrides(cfg: dict) -> None:
        start = os.environ.get("XINGBA_SPA_START_PAGE") or os.environ.get(
            "XINGBA_START_PAGE"
        ) or os.environ.get("START_PAGE")
        end = os.environ.get("XINGBA_SPA_END_PAGE") or os.environ.get(
            "XINGBA_END_PAGE"
        ) or os.environ.get("END_PAGE")
        count = os.environ.get("XINGBA_SPA_PAGE_COUNT") or os.environ.get(
            "XINGBA_PAGE_COUNT"
        )
        rng = os.environ.get("XINGBA_SPA_RANGE_DAYS")
        size = os.environ.get("XINGBA_SPA_PAGE_SIZE")
        if start:
            cfg["start_page"] = int(start)
        if end:
            cfg["end_page"] = int(end)
        if count:
            cfg["page_count"] = int(count)
        if rng:
            cfg["range_days"] = int(rng) if rng != "all" else None
        if size:
            cfg["page_size"] = int(size)

    @staticmethod
    def _join_text(item: dict) -> str:
        parts: list[str] = []
        desc = item.get("desc")
        if isinstance(desc, str) and desc.strip():
            parts.append(desc)
        for block in item.get("text") or []:
            if isinstance(block, dict):
                content = block.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content)
            elif isinstance(block, str) and block.strip():
                parts.append(block)
        return "\n".join(parts)

    @staticmethod
    def _normalize_attachments(attachments: list[Any]) -> list[dict]:
        out: list[dict] = []
        for att in attachments:
            if not isinstance(att, dict):
                continue
            file_obj = att.get("file") if isinstance(att.get("file"), dict) else att
            out.append(
                {
                    "name": file_obj.get("name") or "",
                    "size": file_obj.get("size"),
                    "mime": file_obj.get("mime") or "",
                    "hash": str(file_obj.get("hash") or ""),
                }
            )
        return out

    def _extract_links(self, text: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        def add(link: str) -> None:
            link = link.strip().rstrip(".,;，。）)]}")
            if not link or link in seen:
                return
            seen.add(link)
            found.append(link)

        for m in self.MAGNET_RE.findall(text or ""):
            add(m)
        for m in self.ED2K_RE.findall(text or ""):
            add(m)
        for m in self.CLOUD_RE.findall(text or ""):
            add(m)
        for h in self.HASH_RE.findall(text or ""):
            add(f"magnet:?xt=urn:btih:{h.upper()}")
        return found

    @staticmethod
    def _ts_to_dt(ts: Any) -> datetime | None:
        try:
            n = int(ts)
        except Exception:
            return None
        if n <= 0:
            return None
        try:
            return datetime.fromtimestamp(n, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            return None

    @staticmethod
    def _record_payload(row: dict) -> dict:
        """JSON-safe payload for spider_data_records (UI)."""
        published = row.get("published_at")
        if isinstance(published, datetime):
            published = published.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "thread_id": row.get("post_id"),
            "post_id": row.get("post_id"),
            "eid": row.get("eid"),
            "forum_id": row.get("category_id"),
            "forum_name": row.get("forum_name"),
            "title": row.get("title"),
            "tags": row.get("tags") or [],
            "category": ",".join(row.get("tags") or []),
            "published_at": published or "",
            "create_time": row.get("create_time"),
            "download_links": row.get("download_links") or [],
            "attachments": row.get("attachments") or [],
            "text_preview": row.get("text_preview") or "",
            "source_page": row.get("source_page"),
        }


CrawlerRegistry.register(XingbaSpaForumCrawler)
