"""豆瓣电影 Top 250 爬虫"""

import re
import time
import requests
from bs4 import BeautifulSoup
from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta


class DoubanTop250Crawler(BaseCrawler):
    meta = CrawlerMeta(
        name="豆瓣电影Top250",
        slug="douban-top250",
        description="爬取豆瓣电影 Top 250 榜单完整数据",
        schedule="0 3 * * 1",  # 每周一凌晨3点
        config={"retry_limit": 3},
    )

    BASE_URL = "https://movie.douban.com/top250"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://movie.douban.com/",
    }

    def crawl(self) -> list[dict]:
        records = []

        for start in range(0, 250, 25):
            self.wait_if_paused()
            if self.should_stop:
                break

            page_num = start // 25 + 1
            self.logger.info(f"Fetching page {page_num}/10 (start={start})")

            resp = requests.get(
                self.BASE_URL,
                params={"start": str(start), "filter": ""},
                headers=self.HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for item in soup.select("div.item"):
                rank_el = item.select_one("em")
                pic_el = item.select_one("img")
                title_el = item.select_one(".hd a")
                info_el = item.select_one(".bd p")
                rating_el = item.select_one(".rating_num")
                people_el = item.select_one(".star span:last-child")
                quote_el = item.select_one(".inq")
                link = title_el.get("href", "") if title_el else ""

                # 解析标题（可能有多个）
                titles = [s.get_text(strip=True) for s in (title_el.select("span") if title_el else [])]
                main_title = titles[0] if titles else ""
                alt_titles = " / ".join(titles[1:]) if len(titles) > 1 else ""

                # 解析导演/演员/年份/地区/类型
                info_text = info_el.get_text("\n", strip=True) if info_el else ""
                director = ""
                actors = ""
                year = ""
                region = ""
                genre = ""
                lines = [l.strip() for l in info_text.split("\n") if l.strip()]
                if lines:
                    first = lines[0]
                    m_dir = re.search(r"导演:\s*(.+?)(?:\s+主演:|$)", first)
                    if m_dir:
                        director = m_dir.group(1).strip().rstrip("/").strip()
                    m_act = re.search(r"主演:\s*(.+)", first)
                    if m_act:
                        actors = m_act.group(1).strip().rstrip("/").strip()
                if len(lines) > 1:
                    parts = [p.strip() for p in lines[1].split("/")]
                    if parts:
                        year = parts[0].strip()
                    if len(parts) > 1:
                        region = parts[1].strip()
                    if len(parts) > 2:
                        genre = parts[2].strip()

                rating_count = ""
                if people_el:
                    rating_count = people_el.get_text(strip=True).replace("人评价", "")

                records.append({
                    "data": {
                        "rank": int(rank_el.get_text(strip=True)) if rank_el else 0,
                        "title": main_title,
                        "alt_titles": alt_titles,
                        "year": year,
                        "region": region,
                        "genre": genre,
                        "director": director,
                        "actors": actors,
                        "rating": float(rating_el.get_text(strip=True)) if rating_el else 0,
                        "rating_count": rating_count,
                        "quote": quote_el.get_text(strip=True) if quote_el else "",
                        "cover": pic_el.get("src", "") if pic_el else "",
                        "douban_url": link,
                    },
                    "url": link,
                })

            time.sleep(2)  # 礼貌间隔，避免被封

        self.logger.info(f"Fetched {len(records)} movies total")
        return records


CrawlerRegistry.register(DoubanTop250Crawler)
