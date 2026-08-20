"""中国裁判文书网爬虫。

默认案件类型：强奸罪（s13=166），按裁判日期倒序（s50:desc）。
修改 meta.config 中的 s13 / s16 即可切换罪名。

推荐：python wenshu_save_session.py 保存登录态后自动爬取。
也可设置 WENSHU_COOKIE（SESSION），但登录态易过期且无法跨环境复用。
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime
from urllib.parse import quote

from framework import BaseCrawler, CrawlerRegistry
from framework.base import CrawlerMeta
from framework.wenshu_crypto import decrypt, make_ciphertext, make_token, today_iv

try:
    from framework.wenshu_browser import WenshuBrowserClient, _storage_state_path
    _HAS_BROWSER = True
except ImportError:
    _HAS_BROWSER = False

try:
    from curl_cffi import requests as http
    _IMPERSONATE = "chrome131"
except ImportError:
    import requests as http  # type: ignore
    _IMPERSONATE = None


# 常见刑事罪名 s13 编码（不完全列表，可按需补充）
CRIME_CODES = {
    "故意杀人罪": "121",
    "故意伤害罪": "134",
    "强奸罪": "166",
    "抢劫罪": "236",
    "盗窃罪": "264",
    "诈骗罪": "266",
}


class WenshuRapeCrawler(BaseCrawler):
    meta = CrawlerMeta(
        name="裁判文书网-强奸罪",
        slug="wenshu-rape",
        description="爬取中国裁判文书网「强奸罪」最新裁判文书（可改 s13/s16 切换罪名）",
        schedule="0 2 * * *",
        config={
            "retry_limit": 3,
            "s13": "166",
            "s16": "强奸罪",
            "page_size": 15,
            "max_pages": 5,
            "sort_fields": "s50:desc",
        },
    )

    VIEW_W = "1007"
    VIEW_H = "611"

    API_URL = "https://wenshu.court.gov.cn/website/parse/rest.q4w"
    LIST_CFG = "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@queryDoc"
    LEFT_CFG = "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@leftDataItem"
    DETAIL_CFG = "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@docInfoSearch"
    GROUP_FIELDS = "s45;s11;s4;s33;s42;s8;s6;s44"

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def __init__(self):
        super().__init__()
        self._browser_client: WenshuBrowserClient | None = None
        self._use_browser = _HAS_BROWSER and os.path.isfile(_storage_state_path())
        if self._use_browser:
            self.logger.info(f"Using Playwright storage: {_storage_state_path()}")
            return

        self.session = http.Session()
        cookie = os.environ.get("WENSHU_COOKIE", "").strip()
        if not cookie:
            raise RuntimeError(
                "缺少登录态。请运行 python wenshu_save_session.py，"
                "或在 .env 配置 WENSHU_COOKIE=SESSION=..."
            )
        self._apply_cookie_header(cookie)
        self._verification_token = make_token()
        if _IMPERSONATE:
            self.logger.info(f"HTTP client: curl_cffi impersonate={_IMPERSONATE}")
        else:
            self.logger.warning("curl_cffi 未安装，可能被文书网 WAF 拦截")

    def _apply_cookie_header(self, cookie_header: str):
        for part in cookie_header.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            self.session.cookies.set(name.strip(), value.strip(), domain="wenshu.court.gov.cn")

    def _request(self, method: str, url: str, **kwargs):
        if _IMPERSONATE:
            kwargs.setdefault("impersonate", _IMPERSONATE)
        if method == "GET":
            return self.session.get(url, **kwargs)
        return self.session.post(url, **kwargs)

    def _warmup(self, page_id: str, s16: str, s13: str):
        """模拟浏览器：打开列表页 → leftDataItem 初始化 → 再 queryDoc 拉列表。"""
        base_headers = self._headers(s16, "166", page_id)
        self._request("GET", "https://wenshu.court.gov.cn/", headers=base_headers, timeout=30)
        list_url = (
            "https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html"
            f"?pageId={page_id}&s16={quote(s16)}&s13=166"
        )
        self._request("GET", list_url, headers={**base_headers, "Referer": "https://wenshu.court.gov.cn/"}, timeout=30)

        # 浏览器会先调 leftDataItem（你提供的 fetch），不需要 ciphertext
        left_payload = {
            "pageId": page_id,
            "s16": s16,
            "s13": s13,
            "groupFields": self.GROUP_FIELDS,
            "queryCondition": json.dumps([{"key": "s13", "value": s13}], ensure_ascii=False, separators=(",", ":")),
            "cfg": self.LEFT_CFG,
            "__RequestVerificationToken": self._verification_token,
            "wh": self.VIEW_W,
            "ww": self.VIEW_H,
            "cs": "0",
        }
        try:
            data = self._post_raw(left_payload, s16, s13, page_id)
            if str(data.get("code")) in ("9", "-4") or data.get("success") is False:
                self.logger.warning(f"leftDataItem auth failed: code={data.get('code')}")
            else:
                self.logger.info("leftDataItem warmup ok")
        except Exception as e:
            self.logger.warning(f"leftDataItem warmup failed (continuing): {e}")

        self.logger.info(f"Session ready, cookies: {list(self.session.cookies.keys())}")

    def _resolve_page_id(self) -> str:
        env_id = os.environ.get("WENSHU_PAGE_ID", "").strip()
        if env_id:
            return env_id
        return secrets.token_hex(16)

    def crawl(self) -> list[dict]:
        if self._use_browser:
            return self._crawl_browser()
        return self._crawl_http()

    def _crawl_browser(self) -> list[dict]:
        cfg = self.meta.config
        s13 = str(cfg.get("s13") or "166")
        s16 = str(cfg.get("s16") or "强奸罪")
        page_size = int(cfg.get("page_size") or 15)
        max_pages = int(cfg.get("max_pages") or 5)
        sort_fields = str(cfg.get("sort_fields") or "s50:desc")
        page_id = self._resolve_page_id()

        records: list[dict] = []
        seen: set[str] = set()

        with WenshuBrowserClient() as client:
            client.warmup(page_id, s16, s13)
            for page_num in range(1, max_pages + 1):
                self.wait_if_paused()
                if self.should_stop:
                    break
                self.logger.info(f"Fetching list page {page_num}/{max_pages} s13={s13} {s16}")
                body = client.fetch_list(page_id, s13, s16, page_num, page_size, sort_fields)
                docs = self._parse_list(body)
                if not docs:
                    break
                page_new = self._collect_docs(records, seen, docs, page_id, s16, s13, client)
                self.logger.info(f"Page {page_num}: {len(docs)} items, {page_new} unique")
                if len(docs) < page_size:
                    break
                time.sleep(1.5)

        records.sort(key=self._record_sort_key, reverse=True)
        self.logger.info(f"Fetched {len(records)} documents total")
        return records

    def _collect_docs(
        self,
        records: list[dict],
        seen: set[str],
        docs: list[dict],
        page_id: str,
        s16: str,
        s13: str,
        client: WenshuBrowserClient | None = None,
    ) -> int:
        page_new = 0
        for doc in docs:
            if self.should_stop:
                break
            doc_id = str(doc.get("rowkey") or doc.get("s5") or doc.get("docid") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            detail = {}
            try:
                if client:
                    detail = client.fetch_detail(page_id, doc_id, s16, s13)
                else:
                    detail = self._fetch_detail(page_id, doc_id, s16, s13)
                time.sleep(0.8)
            except Exception as e:
                self.logger.warning(f"Detail fetch failed for {doc_id}: {e}")

            url = f"https://wenshu.court.gov.cn/website/wenshu/181107ANFZ0BXSK4/index.html?docId={doc_id}"
            records.append({
                "data": {
                    "doc_id": doc_id,
                    "title": doc.get("s1") or detail.get("title") or "",
                    "case_no": doc.get("s7") or detail.get("s7") or "",
                    "court": doc.get("s2") or detail.get("s2") or "",
                    "case_type": s16,
                    "crime_code": s13,
                    "judge_date": doc.get("s31") or doc.get("s29") or "",
                    "procedure": doc.get("s8") or "",
                    "content": detail.get("qwContent") or detail.get("s25") or detail.get("content") or "",
                    "raw": {k: v for k, v in doc.items() if k != "s25"},
                },
                "url": url,
            })
            page_new += 1
        return page_new

    def _crawl_http(self) -> list[dict]:
        cfg = self.meta.config
        s13 = str(cfg.get("s13") or "166")
        s16 = str(cfg.get("s16") or "强奸罪")
        page_size = int(cfg.get("page_size") or 15)
        max_pages = int(cfg.get("max_pages") or 5)
        sort_fields = str(cfg.get("sort_fields") or "s50:desc")
        page_id = self._resolve_page_id()
        self._warmup(page_id, s16, s13)

        records: list[dict] = []
        seen: set[str] = set()

        for page_num in range(1, max_pages + 1):
            self.wait_if_paused()
            if self.should_stop:
                break

            self.logger.info(f"Fetching list page {page_num}/{max_pages} s13={s13} {s16}")
            payload = self._list_payload(page_id, s13, s16, page_num, page_size, sort_fields)
            body = self._post(payload, referrer_s16=s16, s13=s13, page_id=page_id)
            docs = self._parse_list(body)
            if not docs:
                self.logger.info("No more documents on this page")
                break

            page_new = 0
            for doc in docs:
                if self.should_stop:
                    break
                doc_id = str(doc.get("rowkey") or doc.get("s5") or doc.get("docid") or "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)

                detail = {}
                try:
                    detail = self._fetch_detail(page_id, doc_id, s16, s13)
                    time.sleep(0.8)
                except Exception as e:
                    self.logger.warning(f"Detail fetch failed for {doc_id}: {e}")

                url = f"https://wenshu.court.gov.cn/website/wenshu/181107ANFZ0BXSK4/index.html?docId={doc_id}"
                records.append({
                    "data": {
                        "doc_id": doc_id,
                        "title": doc.get("s1") or detail.get("title") or "",
                        "case_no": doc.get("s7") or detail.get("s7") or "",
                        "court": doc.get("s2") or detail.get("s2") or "",
                        "case_type": s16,
                        "crime_code": s13,
                        "judge_date": doc.get("s31") or doc.get("s29") or "",
                        "procedure": doc.get("s8") or "",
                        "content": detail.get("qwContent") or detail.get("s25") or detail.get("content") or "",
                        "raw": {k: v for k, v in doc.items() if k != "s25"},
                    },
                    "url": url,
                })
                page_new += 1

            self.logger.info(f"Page {page_num}: {len(docs)} items, {page_new} unique")
            if len(docs) < page_size:
                break
            time.sleep(1.5)

        records.sort(key=self._record_sort_key, reverse=True)
        self.logger.info(f"Fetched {len(records)} documents total")
        return records

    @staticmethod
    def _normalize_judge_date(value: str) -> str:
        """Normalize judge_date to YYYYMMDDHHMMSS for stable sorting."""
        if not value:
            return ""
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y%m%d000000")
            except ValueError:
                continue
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 14:
            return digits[:14]
        if len(digits) >= 8:
            return f"{digits[:8]}000000"
        return ""

    def _record_sort_key(self, record: dict) -> tuple[int, str, str]:
        data = record.get("data", {}) if isinstance(record, dict) else {}
        judge_date = self._normalize_judge_date(str(data.get("judge_date") or ""))
        doc_id = str(data.get("doc_id") or "")
        return (1 if judge_date else 0, judge_date, doc_id)

    def _headers(self, s16: str, s13: str, page_id: str) -> dict:
        referer = (
            "https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html"
            f"?pageId={page_id}&s16={quote(s16)}&s13={s13}"
        )
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://wenshu.court.gov.cn",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

    def _list_payload(self, page_id: str, s13: str, s16: str, page_num: int, page_size: int, sort_fields: str) -> dict:
        condition = json.dumps([{"key": "s13", "value": s13}], ensure_ascii=False, separators=(",", ":"))
        return {
            "pageId": page_id,
            "s16": s16,
            "s13": s13,
            "sortFields": sort_fields,
            "ciphertext": make_ciphertext(),
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "queryCondition": condition,
            "cfg": self.LIST_CFG,
            "__RequestVerificationToken": self._verification_token,
            "wh": self.VIEW_W,
            "ww": self.VIEW_H,
            "cs": "0",
        }

    def _post_raw(self, payload: dict, referrer_s16: str, s13: str, page_id: str) -> dict:
        resp = self._request(
            "POST",
            self.API_URL,
            data=payload,
            headers=self._headers(referrer_s16, s13, page_id),
            timeout=40,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, payload: dict, referrer_s16: str, s13: str, page_id: str) -> dict:
        last_error: Exception | None = None
        resp = None
        for attempt in range(4):
            try:
                resp = self._request(
                    "POST",
                    self.API_URL,
                    data=payload,
                    headers=self._headers(referrer_s16, s13, page_id),
                    timeout=40,
                )
                resp.raise_for_status()
                break
            except Exception as e:
                last_error = e
                self.logger.warning(f"Request failed ({attempt + 1}/4): {e}")
                time.sleep(2 + attempt)
        else:
            raise RuntimeError(f"Wenshu request failed after retries: {last_error}")

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"Non-JSON response: {resp.text[:400]}")

        code = data.get("code")
        if data.get("success") is False or str(code) not in ("None", "1", "0", "success"):
            desc = data.get("description") or json.dumps(data, ensure_ascii=False)[:300]
            if str(code) in ("9", "-4"):
                raise RuntimeError(f"文书网未授权(code={code})。登录 Cookie 可能失效。{desc}")
            raise RuntimeError(f"Wenshu API error code={code}: {desc}")

        secret = data.get("secretKey")
        result = data.get("result")
        if secret and result:
            try:
                plain = decrypt(result, secret, today_iv())
                return json.loads(plain)
            except Exception as e:
                self.logger.warning(f"Decrypt failed: {e}; keys={list(data.keys())}")
                return data
        return data

    def _parse_list(self, body: dict) -> list[dict]:
        if not isinstance(body, dict):
            return []
        query = body.get("queryResult") or body.get("data") or body
        if isinstance(query, dict):
            result_list = query.get("resultList") or query.get("list") or query.get("data") or []
            if isinstance(result_list, list):
                return [x for x in result_list if isinstance(x, dict)]
        if isinstance(body.get("resultList"), list):
            return body["resultList"]
        self.logger.warning(f"Unexpected list shape keys={list(body.keys())[:20]}")
        return []

    def _fetch_detail(self, page_id: str, doc_id: str, s16: str, s13: str) -> dict:
        payload = {
            "pageId": page_id,
            "ciphertext": make_ciphertext(),
            "cfg": self.DETAIL_CFG,
            "docId": doc_id,
            "__RequestVerificationToken": self._verification_token,
            "wh": self.VIEW_W,
            "ww": self.VIEW_H,
            "cs": "0",
        }
        body = self._post(payload, referrer_s16=s16, s13=s13, page_id=page_id)
        if isinstance(body, dict):
            return body.get("DocInfoVo") or body.get("data") or body
        return {}


CrawlerRegistry.register(WenshuRapeCrawler)
