"""通过 Playwright 浏览器上下文请求文书网 API（绕过 WAF + 登录态绑定）。"""

from __future__ import annotations

import json
import os
from urllib.parse import quote

from framework.wenshu_crypto import decrypt, make_ciphertext, make_token, today_iv

LIST_PAGE = "https://wenshu.court.gov.cn/website/wenshu/181217BMTKHNT2W0/index.html"
API_URL = "https://wenshu.court.gov.cn/website/parse/rest.q4w"
LIST_CFG = "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@queryDoc"
DETAIL_CFG = "com.lawyee.judge.dc.parse.dto.SearchDataDsoDTO@docInfoSearch"


def _storage_state_path() -> str:
    path = os.environ.get("WENSHU_STORAGE_STATE", "").strip()
    if not path:
        path = os.path.join(os.path.dirname(__file__), "..", "wenshu_storage_state.json")
    return os.path.abspath(path)


def _launch_context(playwright):
    from playwright.sync_api import BrowserContext

    state_path = _storage_state_path()
    if not os.path.isfile(state_path):
        raise RuntimeError(
            f"缺少登录态文件 {state_path}。"
            "请先运行: python wenshu_save_session.py"
        )

    for launch_kwargs in (
        {"channel": "chrome", "headless": True, "args": ["--disable-blink-features=AutomationControlled"]},
        {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]},
    ):
        try:
            browser = playwright.chromium.launch(**launch_kwargs)
            ctx: BrowserContext = browser.new_context(storage_state=state_path, locale="zh-CN")
            return browser, ctx
        except Exception:
            continue
    raise RuntimeError("无法启动 Chrome/Chromium")


def _list_url(page_id: str, s16: str, s13: str) -> str:
    return f"{LIST_PAGE}?pageId={page_id}&s16={quote(s16)}&s13={s13}"


def _ensure_page(page, page_id: str, s16: str, s13: str):
    url = _list_url(page_id, s16, s13)
    if page.url != url:
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)


_FETCH_JS = """
async (args) => {
    const body = new URLSearchParams({
        pageId: args.pageId,
        cfg: args.cfg,
        wh: args.wh,
        ww: args.ww,
        cs: '0',
    });
    if (args.s16) body.set('s16', args.s16);
    if (args.s13) body.set('s13', args.s13);
    if (args.sortFields) body.set('sortFields', args.sortFields);
    if (args.pageNum != null) body.set('pageNum', String(args.pageNum));
    if (args.pageSize != null) body.set('pageSize', String(args.pageSize));
    if (args.queryCondition) body.set('queryCondition', args.queryCondition);
    if (args.docId) body.set('docId', args.docId);
    if (args.ciphertext) body.set('ciphertext', args.ciphertext);
    if (args.token) body.set('__RequestVerificationToken', args.token);

    // Prefer explicit values from Python; only try page functions as best-effort.
    if (!body.get('ciphertext')) {
        try {
            if (window.$ && $.WebSite && typeof $.WebSite.cipher === 'function') {
                body.set('ciphertext', $.WebSite.cipher());
            } else if (typeof cipher === 'function') {
                body.set('ciphertext', cipher());
            }
        } catch (_) {}
    }
    if (!body.get('__RequestVerificationToken')) {
        try {
            if (window.$ && $.WebSite && typeof $.WebSite.random === 'function') {
                body.set('__RequestVerificationToken', $.WebSite.random(24));
            }
        } catch (_) {}
    }
    const r = await fetch('""" + API_URL + """', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: body.toString(),
    });
    return await r.json();
}
"""


def _parse_api_response(data: dict) -> dict:
    code = data.get("code")
    if data.get("success") is False or str(code) not in ("None", "1", "0", "success"):
        desc = data.get("description") or json.dumps(data, ensure_ascii=False)[:300]
        raise RuntimeError(f"文书网 API code={code}: {desc}")

    secret = data.get("secretKey")
    result = data.get("result")
    if secret and result:
        plain = decrypt(result, secret, today_iv())
        return json.loads(plain)
    return data


class WenshuBrowserClient:
    """复用已保存的 Playwright 登录态，在页面内调用官网 JS 发请求。"""

    VIEW_W = "1007"
    VIEW_H = "611"

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._ctx = None
        self._page = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser, self._ctx = _launch_context(self._playwright)
        self._page = self._ctx.new_page()
        return self

    def __exit__(self, *args):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def warmup(self, page_id: str, s16: str, s13: str):
        _ensure_page(self._page, page_id, s16, s13)

    def fetch_list(
        self,
        page_id: str,
        s13: str,
        s16: str,
        page_num: int,
        page_size: int,
        sort_fields: str,
    ) -> dict:
        _ensure_page(self._page, page_id, s16, s13)
        condition = json.dumps([{"key": "s13", "value": s13}], ensure_ascii=False, separators=(",", ":"))
        raw = self._page.evaluate(
            _FETCH_JS,
            {
                "pageId": page_id,
                "s16": s16,
                "s13": s13,
                "sortFields": sort_fields,
                "pageNum": page_num,
                "pageSize": page_size,
                "queryCondition": condition,
                "cfg": LIST_CFG,
                "wh": self.VIEW_W,
                "ww": self.VIEW_H,
                "ciphertext": make_ciphertext(),
                "token": make_token(),
            },
        )
        return _parse_api_response(raw)

    def fetch_detail(self, page_id: str, doc_id: str, s16: str, s13: str) -> dict:
        _ensure_page(self._page, page_id, s16, s13)
        raw = self._page.evaluate(
            _FETCH_JS,
            {
                "pageId": page_id,
                "docId": doc_id,
                "cfg": DETAIL_CFG,
                "wh": self.VIEW_W,
                "ww": self.VIEW_H,
                "ciphertext": make_ciphertext(),
                "token": make_token(),
            },
        )
        body = _parse_api_response(raw)
        if isinstance(body, dict):
            return body.get("DocInfoVo") or body.get("data") or body
        return {}
