"""杏吧新版 SPA API 客户端（登录 / 线路 / 列表分页）。"""

from __future__ import annotations

import hashlib
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
FALLBACK_Z_S3 = "https://photos.x5ewt.com"

JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")


def _bdecode(data: bytes, i: int = 0) -> tuple[Any, int]:
    """最小 bencode 解码（只够算 infohash / magnet）。"""
    if i >= len(data):
        raise ValueError("truncated bencode")
    c = data[i : i + 1]
    if c == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1 : j]), j + 1
    if c == b"l":
        out: list[Any] = []
        i += 1
        while data[i : i + 1] != b"e":
            v, i = _bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        out_d: dict[bytes, Any] = {}
        i += 1
        while data[i : i + 1] != b"e":
            k, i = _bdecode(data, i)
            v, i = _bdecode(data, i)
            out_d[k] = v
        return out_d, i + 1
    colon = data.index(b":", i)
    n = int(data[i:colon])
    start = colon + 1
    end = start + n
    return data[start:end], end


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
        self.z_s3: str = FALLBACK_Z_S3
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
                z_hosts = _prefer_hosts(_as_list(data.get("z-s3")), FALLBACK_Z_S3)
                if z_hosts:
                    self.z_s3 = z_hosts[0]
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

    def _new_session(self) -> requests.Session:
        """线程内独立 Session（共享同一套鉴权头）。"""
        s = requests.Session()
        s.headers.update(dict(self.session.headers))
        return s

    def trend_read(
        self,
        for_id: str,
        *,
        post_type: int = 1,
        session: requests.Session | None = None,
    ) -> dict[str, Any]:
        """详情：含 attachments[].resource.name（真实 CDN 文件名）。"""
        sess = session or self.session
        body = {"for_id": str(for_id), "type": int(post_type)}
        last_err: Exception | None = None
        for social in self.socials:
            try:
                resp = sess.post(
                    f"{social}/Social/Trend/Read",
                    json=body,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if str(data.get("status", "")).upper() != "SUCCESS":
                    raise RuntimeError(f"trend_read failed: {data}")
                self.socials = [social] + [x for x in self.socials if x != social]
                msg = data.get("msg")
                return msg if isinstance(msg, dict) else {}
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Social/Trend/Read failed: {last_err}")

    def trend_download(
        self,
        *,
        for_id: str,
        file_hash: str,
        post_type: int = 1,
        download_type: int = 1,
    ) -> dict[str, Any]:
        """登记下载（站点点击附件时会先调这个），不返回种子内容。"""
        body = {
            "type": int(post_type),
            "download_type": int(download_type),
            "for_id": str(for_id),
            "hash": str(file_hash),
        }
        last_err: Exception | None = None
        for social in self.socials:
            try:
                resp = self.session.post(
                    f"{social}/Social/Trend/Download",
                    json=body,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if str(data.get("status", "")).upper() != "SUCCESS":
                    raise RuntimeError(f"trend_download failed: {data}")
                self.socials = [social] + [x for x in self.socials if x != social]
                return data if isinstance(data, dict) else {}
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Social/Trend/Download failed: {last_err}")

    def torrent_cdn_url(self, resource_name: str) -> str:
        """resource.name → CDN 上的 .torrent 直链（迅雷常拉不动该域名）。"""
        name = (resource_name or "").lstrip("/")
        if not name:
            return ""
        return f"{self.z_s3.rstrip('/')}/{name}"

    def fetch_torrent_bytes(
        self,
        torrent_url: str,
        *,
        session: requests.Session | None = None,
    ) -> bytes:
        sess = session or self.session
        resp = sess.get(torrent_url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.content
        if not data.startswith(b"d") or b"4:info" not in data:
            raise RuntimeError(f"not a torrent: {torrent_url} len={len(data)}")
        return data

    @staticmethod
    def torrent_to_magnet(raw: bytes) -> str:
        """从 .torrent 字节算出 magnet（迅雷可直接添加）。"""
        meta, _ = _bdecode(raw, 0)
        if not isinstance(meta, dict):
            raise RuntimeError("invalid torrent root")
        info = meta.get(b"info")
        if not isinstance(info, dict):
            raise RuntimeError("torrent missing info")
        idx = raw.index(b"4:info") + 6
        _, end = _bdecode(raw, idx)
        infohash = hashlib.sha1(raw[idx:end]).hexdigest().upper()
        # 迅雷只需 infohash；不拼 announce-list（往往几十个 &tr=，又长又无用）
        return f"magnet:?xt=urn:btih:{infohash}"

    def resolve_attachment_urls(
        self,
        for_id: str,
        *,
        register_download: bool = False,
        session: requests.Session | None = None,
    ) -> list[dict[str, Any]]:
        """详情附件 → torrent_url + magnet（优先用 magnet 给下载器）。

        register_download=False：跳过站点登记接口（CDN 可直接拉种子，省一次 RTT）。
        """
        sess = session or self.session
        detail = self.trend_read(for_id, session=sess)
        out: list[dict[str, Any]] = []
        for att in detail.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            file_obj = att.get("file") if isinstance(att.get("file"), dict) else {}
            resource = att.get("resource") if isinstance(att.get("resource"), dict) else {}
            resource_name = str(resource.get("name") or "")
            file_hash = str(file_obj.get("hash") or "")
            torrent_url = self.torrent_cdn_url(resource_name)
            magnet = ""
            if torrent_url:
                if register_download and file_hash:
                    try:
                        self.trend_download(for_id=for_id, file_hash=file_hash)
                    except Exception:
                        pass
                try:
                    raw = self.fetch_torrent_bytes(torrent_url, session=sess)
                    magnet = self.torrent_to_magnet(raw)
                except Exception:
                    magnet = ""
            out.append(
                {
                    "name": file_obj.get("name") or resource_name or "",
                    "size": file_obj.get("size"),
                    "mime": file_obj.get("mime") or "",
                    "hash": file_hash,
                    "resource_name": resource_name,
                    "torrent_url": torrent_url,
                    "magnet": magnet,
                }
            )
        return out

    def resolve_attachments_many(
        self,
        post_ids: list[str],
        *,
        workers: int = 8,
    ) -> dict[str, list[dict[str, Any]] | Exception]:
        """并行解析多帖附件；返回 post_id → attachments 或 Exception。"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        ids = [str(p).strip() for p in post_ids if str(p).strip()]
        if not ids:
            return {}
        workers = max(1, min(int(workers or 1), 16, len(ids)))

        def _one(pid: str) -> tuple[str, list[dict[str, Any]] | Exception]:
            sess = self._new_session()
            try:
                return pid, self.resolve_attachment_urls(pid, session=sess)
            except Exception as e:
                return pid, e
            finally:
                sess.close()

        out: dict[str, list[dict[str, Any]] | Exception] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_one, pid) for pid in ids]
            for fut in as_completed(futs):
                pid, res = fut.result()
                out[pid] = res
        return out

    def _guest_token_from_ssr(self) -> str:
        url = (
            f"{self.site_base}/mainPage/"
            "666a736faa91b688401ae8da/132/798?filter=publish&range=all"
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
