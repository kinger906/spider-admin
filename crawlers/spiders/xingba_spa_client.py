"""杏吧新版 SPA API 客户端（登录 / 线路 / 列表分页）。"""

from __future__ import annotations

import re
import time
from typing import Any

import requests

BUNDLE_INFO = "1, com.xingba.web.online"
DEFAULT_SITE = "https://www.bin7sha1n.website"
DEFAULT_AUTH_LINE = "https://auth-server.zsxer.top"
FALLBACK_CENTER = "https://center-server.zsxer.top"
FALLBACK_SEARCH = "https://search-server.zsxer.top"
FALLBACK_SOCIAL = "https://social-server.zsxer.top"

JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).rstrip("/") for x in value if x]
    return [str(value).rstrip("/")]


def _prefer_hosts(hosts: list[str], *fallbacks: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for h in list(fallbacks) + [x for x in hosts if "zsxer" in x] + hosts:
        h = h.rstrip("/")
        if not h or h in seen:
            continue
        seen.add(h)
        ordered.append(h)
    return ordered


class XingbaSpaClient:
    def __init__(
        self,
        site_base: str = DEFAULT_SITE,
        user_name: str = "",
        password: str = "",
        timeout: float = 30,
    ):
        self.site_base = site_base.rstrip("/")
        self.user_name = user_name
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/155.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": self.site_base,
                "Referer": f"{self.site_base}/",
                "x-bundle-info": BUNDLE_INFO,
            }
        )
        self.centers: list[str] = [FALLBACK_CENTER]
        self.searches: list[str] = [FALLBACK_SEARCH]
        self.socials: list[str] = [FALLBACK_SOCIAL]
        self.token: str = ""

    def bootstrap(self) -> None:
        self.refresh_lines()
        if self.user_name and self.password:
            self.login(self.user_name, self.password)
        else:
            self.token = self._guest_token_from_ssr()
            if self.token:
                self.session.headers["authorization"] = self.token

    def refresh_lines(self) -> None:
        last_err: Exception | None = None
        for auth in (DEFAULT_AUTH_LINE, "https://auth-server.hhg3e.com"):
            try:
                resp = self.session.get(
                    f"{auth}/Auth/Guest/Token",
                    params={"package_id": 1},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    continue
                self.centers = _prefer_hosts(
                    _as_list(data.get("center-server")), FALLBACK_CENTER
                )
                self.searches = _prefer_hosts(
                    _as_list(data.get("search-server")), FALLBACK_SEARCH
                )
                self.socials = _prefer_hosts(
                    _as_list(data.get("social-server")), FALLBACK_SOCIAL
                )
                return
            except Exception as e:
                last_err = e
        if last_err:
            # keep fallbacks
            pass

    def login(self, user_name: str, password: str) -> str:
        body = {
            "user_name": user_name,
            "pass_word": password,
            "package_id": 1,
        }
        last_err: Exception | None = None
        for center in self.centers:
            try:
                resp = self.session.post(
                    f"{center}/User/Account/Login",
                    json=body,
                    timeout=self.timeout,
                )
                token = resp.headers.get("Token") or resp.headers.get("token") or ""
                if not token and resp.ok:
                    # rare: token in body
                    try:
                        token = self._find_jwt(resp.json()) or ""
                    except Exception:
                        token = ""
                if resp.status_code == 200 and token:
                    self.token = token
                    self.session.headers["authorization"] = token
                    # promote working center
                    self.centers = [center] + [c for c in self.centers if c != center]
                    return token
                last_err = RuntimeError(f"{center} login -> {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                last_err = e
        raise RuntimeError(f"SPA login failed: {last_err}")

    def query_posts(
        self,
        *,
        category_id: str,
        page: int,
        limit: int = 16,
        range_days: int | None = 180,
        sort_field: str = "create_time",
    ) -> dict[str, Any]:
        """按新主题排序拉取一页帖子。返回 {count, list}。"""
        and_filters: list[dict[str, Any]] = [
            {"field": "categories_id", "op": "$eq", "value": str(category_id)},
            {"field": "status", "op": "$in", "value": [1, 8]},
        ]
        if range_days is not None and int(range_days) > 0:
            gte = int(time.time()) - int(range_days) * 24 * 3600
            and_filters.append(
                {"field": "create_time", "op": "$gte", "value": gte}
            )
        payload = [
            {
                "name": "social.post",
                "limit": int(limit),
                "page": int(page),
                "and": and_filters,
                "sort": [{"field": sort_field, "order": "DESC"}],
            }
        ]
        last_err: Exception | None = None
        for search in self.searches:
            try:
                resp = self.session.post(
                    f"{search}/Search/Social/Query",
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 406 and not self.token:
                    # retry after SSR guest token
                    self.token = self._guest_token_from_ssr()
                    if self.token:
                        self.session.headers["authorization"] = self.token
                        resp = self.session.post(
                            f"{search}/Search/Social/Query",
                            json=payload,
                            timeout=self.timeout,
                        )
                resp.raise_for_status()
                data = resp.json()
                if str(data.get("status", "")).upper() != "SUCCESS":
                    raise RuntimeError(f"query failed: {data}")
                block = (data.get("msg") or [None])[0] or {}
                self.searches = [search] + [x for x in self.searches if x != search]
                return {
                    "count": int(block.get("count") or 0),
                    "list": list(block.get("list") or []),
                }
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Search/Social/Query failed: {last_err}")

    def _guest_token_from_ssr(self) -> str:
        url = (
            f"{self.site_base}/mainPage/"
            "666a736faa91b688401ae8da/132/798?filter=publish&range=180"
        )
        try:
            resp = self.session.get(
                url,
                headers={"Accept": "text/html"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            m = JWT_RE.search(resp.text)
            return m.group(0) if m else ""
        except Exception:
            return ""

    @staticmethod
    def _find_jwt(obj: Any) -> str | None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "token" and isinstance(v, str) and v.startswith("eyJ"):
                    return v
                found = XingbaSpaClient._find_jwt(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = XingbaSpaClient._find_jwt(item)
                if found:
                    return found
        elif isinstance(obj, str) and obj.startswith("eyJ"):
            m = JWT_RE.search(obj)
            return m.group(0) if m else None
        return None
