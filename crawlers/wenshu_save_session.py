"""打开浏览器手动登录文书网，保存 Playwright 登录态供爬虫使用。

用法:
    cd crawlers
    python wenshu_save_session.py

登录成功并看到首页/列表页后，回到终端按 Enter 保存。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

OUTPUT = os.environ.get(
    "WENSHU_STORAGE_STATE",
    os.path.join(os.path.dirname(__file__), "wenshu_storage_state.json"),
)


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit("请先安装: pip install playwright && python -m playwright install chromium") from e

    print("将打开 Chrome，请手动登录 https://wenshu.court.gov.cn")
    print("登录后打开任意文书列表页，确认能正常看到数据，再回到此窗口按 Enter。")
    print(f"登录态将保存到: {os.path.abspath(OUTPUT)}")

    with sync_playwright() as p:
        browser = None
        for launch_kwargs in (
            {"channel": "chrome", "headless": False, "args": ["--disable-blink-features=AutomationControlled"]},
            {"headless": False, "args": ["--disable-blink-features=AutomationControlled"]},
        ):
            try:
                browser = p.chromium.launch(**launch_kwargs)
                break
            except Exception:
                continue
        if browser is None:
            raise SystemExit("无法启动 Chrome/Chromium")

        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        page.goto("https://wenshu.court.gov.cn/", wait_until="domcontentloaded", timeout=60000)
        input("\n>>> 登录完成且列表能加载后，按 Enter 保存登录态...\n")
        ctx.storage_state(path=OUTPUT)
        browser.close()

    print(f"已保存: {os.path.abspath(OUTPUT)}")
    print("现在可运行: python run.py wenshu-rape --trigger manual")


if __name__ == "__main__":
    main()
