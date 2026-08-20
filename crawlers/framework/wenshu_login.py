"""裁判文书网登录：用 Playwright 打开官网，提交账号密码，导出 Cookie。"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()

LOGIN_URL = (
    "https://account.court.gov.cn/#/login"
    "?redirect_uri=https%3A%2F%2Fwenshu.court.gov.cn%2F"
)
HOME_URL = "https://wenshu.court.gov.cn/"


def login_and_get_cookie_header(user: str | None = None, password: str | None = None, timeout_ms: int = 60000) -> str:
    user = user or os.environ.get("WENSHU_USER", "").strip()
    password = password or os.environ.get("WENSHU_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError("请在 crawlers/.env 中配置 WENSHU_USER 和 WENSHU_PASSWORD")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("需要安装 playwright：pip install playwright && python -m playwright install chromium") from e

    with sync_playwright() as p:
        browser = None
        last_err = None
        for launch_kwargs in (
            {"channel": "chrome", "headless": True, "args": ["--disable-blink-features=AutomationControlled"]},
            {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]},
        ):
            try:
                browser = p.chromium.launch(**launch_kwargs)
                break
            except Exception as e:
                last_err = e
        if browser is None:
            raise RuntimeError(f"无法启动 Chrome/Chromium: {last_err}")
        context = browser.new_context(
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        last_nav = None
        for i in range(4):
            try:
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
                last_nav = None
                break
            except Exception as e:
                last_nav = e
                page.wait_for_timeout(2000)
        if last_nav:
            raise RuntimeError(f"打开登录页失败（网站可能重置了连接）: {last_nav}")
        page.wait_for_timeout(3000)
        debug_path = os.path.join(os.path.dirname(__file__), "..", "_wenshu_login_debug.html")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(page.url + "\n\n" + page.content())
        page.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "_wenshu_login.png"), full_page=True)

        frames = [page] + list(page.frames)
        target = page
        for fr in frames:
            try:
                if fr.locator('input[type="password"]').count() > 0:
                    target = fr
                    break
            except Exception:
                pass

        phone = target.locator('input[placeholder*="手机"]')
        if phone.count() == 0:
            phone = target.locator('input[type="text"]')
        pwd = target.locator('input[type="password"]')
        pwd.wait_for(timeout=timeout_ms)
        phone.first.fill(user, timeout=timeout_ms)
        pwd.first.fill(password, timeout=timeout_ms)

        submit = target.locator('[data-action="login-submit"]')
        if submit.count():
            submit.first.click()
        else:
            target.get_by_text("登录", exact=True).first.click()

        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "_wenshu_login_after.png"), full_page=True)

        body_text = page.inner_text("body")
        if "验证码" in body_text or "tianai" in page.content() and "slider" in page.content().lower():
            cap = target.locator(".tianai-captcha, [class*='captcha'], [class*='slider']")
            if cap.count() and cap.first.is_visible():
                raise RuntimeError(
                    "登录需要滑块/图形验证码，无法在无头浏览器里自动完成。"
                    "请在浏览器手动登录文书网后，从 rest.q4w 请求头复制 Cookie 到 crawlers/.env 的 WENSHU_COOKIE。"
                )

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            url = page.url
            cookies = context.cookies()
            names = {c["name"] for c in cookies}
            if "wenshu.court.gov.cn" in url and "account.court.gov.cn" not in url:
                break
            if "SESSION" in names:
                page.goto(HOME_URL, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(2000)
                cookies = context.cookies()
                break
            page.wait_for_timeout(500)
        else:
            names = {c["name"] for c in context.cookies()}
            raise RuntimeError(
                "登录未完成（没有 SESSION Cookie）。"
                f" 当前 URL={page.url} cookies={sorted(names)}。"
                " 多半被验证码拦住，请手动登录后配置 WENSHU_COOKIE。"
            )

        cookies = context.cookies()
        browser.close()

    if not cookies:
        raise RuntimeError("登录后未拿到 Cookie")

    # Playwright cookies -> Cookie header
    parts = []
    for c in cookies:
        if c.get("name") and c.get("value") is not None:
            parts.append(f"{c['name']}={c['value']}")
    header = "; ".join(parts)
    if not header:
        raise RuntimeError("登录 Cookie 为空")
    return header
