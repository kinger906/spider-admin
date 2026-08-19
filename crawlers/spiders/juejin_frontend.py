"""掘金前端最新文章爬虫 - 通过 API 获取文章列表及内容"""

import requests
import time
from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta


class JuejinFrontendCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="掘金前端最新",
        slug="juejin-frontend",
        description="爬取掘金前端频道最新文章标题、摘要及正文内容",
        schedule="0 */4 * * *",
        config={"retry_limit": 3, "page_count": 3},
    )

    API_URL = "https://api.juejin.cn/recommend_api/v1/article/recommend_cate_feed"
    DETAIL_URL = "https://api.juejin.cn/content_api/v1/article/detail"
    CATE_ID = "6809637767543259144"  # 前端分类 ID
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://juejin.cn/",
        "Origin": "https://juejin.cn",
    }

    def crawl(self) -> list[dict]:
        records = []
        page_count = self.meta.config.get("page_count", 3)
        cursor = "0"

        for page in range(page_count):
            self.wait_if_paused()
            if self.should_stop:
                break

            self.logger.info(f"Fetching page {page + 1}/{page_count}, cursor={cursor}")
            payload = {
                "id_type": 2,
                "sort_type": 200,  # 200 = 最新
                "cate_id": self.CATE_ID,
                "cursor": cursor,
                "limit": 20,
            }

            resp = requests.post(self.API_URL, json=payload, headers=self.HEADERS, timeout=30)
            resp.raise_for_status()
            body = resp.json()

            if body.get("err_no") != 0:
                self.logger.warning(f"API error: {body.get('err_msg')}")
                break

            articles = body.get("data", [])
            if not articles:
                break

            cursor = body.get("cursor", str(int(cursor) + 20))

            for item in articles:
                if self.should_stop:
                    break

                info = item.get("article_info", {})
                author = item.get("author_user_info", {})
                article_id = info.get("article_id", "")
                if not article_id:
                    continue

                article_url = f"https://juejin.cn/post/{article_id}"

                # Fetch full article content
                content = self._fetch_content(article_id)

                records.append({
                    "data": {
                        "article_id": article_id,
                        "title": info.get("title", ""),
                        "brief": info.get("brief_content", ""),
                        "content": content,
                        "cover": info.get("cover_image", ""),
                        "author": author.get("user_name", ""),
                        "author_id": author.get("user_id", ""),
                        "digg_count": info.get("digg_count", 0),
                        "view_count": info.get("view_count", 0),
                        "comment_count": info.get("comment_count", 0),
                        "collect_count": info.get("collect_count", 0),
                        "tags": [t.get("tag_name", "") for t in item.get("tags", [])],
                        "created_at": info.get("ctime", ""),
                        "modified_at": info.get("mtime", ""),
                    },
                    "url": article_url,
                })

            time.sleep(1)

        self.logger.info(f"Fetched {len(records)} articles total")
        return records

    def _fetch_content(self, article_id: str) -> str:
        """Fetch the markdown content of a single article."""
        try:
            resp = requests.post(
                self.DETAIL_URL,
                json={"article_id": article_id},
                headers=self.HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("err_no") == 0:
                return body.get("data", {}).get("article_info", {}).get("mark_content", "")
        except Exception as e:
            self.logger.warning(f"Failed to fetch content for {article_id}: {e}")
        return ""


CrawlerRegistry.register(JuejinFrontendCrawler)
