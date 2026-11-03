"""用已保存的 cookie 打开各平台创作者中心（有头浏览器）。"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from playwright.async_api import async_playwright

from conf import BASE_DIR
from myUtils.login import get_browser_options
from utils.base_social_media import set_init_script

# 平台 type -> 创作者中心首页
CREATOR_CENTER_URLS = {
    1: "https://creator.xiaohongshu.com/",
    2: "https://channels.weixin.qq.com/platform",
    3: "https://creator.douyin.com/",
    4: "https://cp.kuaishou.com/",
    5: "https://baijiahao.baidu.com/builder/rc/home",
    6: "https://member.bilibili.com/",
    7: "https://mp.toutiao.com/",
    8: "https://mp.sohu.com/",
    9: "https://www.zhihu.com/creator",
}

PLATFORM_LABELS = {
    1: "小红书",
    2: "视频号",
    3: "抖音",
    4: "快手",
    5: "百家号",
    6: "B站",
    7: "今日头条",
    8: "搜狐",
    9: "知乎",
}


def get_creator_url(platform_type: int) -> str | None:
    return CREATOR_CENTER_URLS.get(platform_type)


def load_account(account_id: int) -> dict:
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, type, filePath, userName, status FROM user_info WHERE id = ?",
            (account_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"账号不存在: id={account_id}")
        return {
            "id": row["id"],
            "type": int(row["type"]),
            "filePath": row["filePath"],
            "userName": row["userName"],
            "status": row["status"],
        }


def cookie_path(file_path: str) -> Path:
    path = Path(BASE_DIR / "cookiesFile" / file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {file_path}")
    return path


def _bilibili_storage_state(cookie_file: Path) -> dict:
    """把 biliup cookie 转成 Playwright storage_state。"""
    payload = json.loads(cookie_file.read_text(encoding="utf-8"))
    raw_cookies = None
    if isinstance(payload, dict):
        cookie_info = payload.get("cookie_info")
        if isinstance(cookie_info, dict):
            raw_cookies = cookie_info.get("cookies")
        if raw_cookies is None:
            raw_cookies = payload.get("cookies")
    if not isinstance(raw_cookies, list) or not raw_cookies:
        raise ValueError("B站 cookie 格式无效，请重新登录")

    cookies = []
    for item in raw_cookies:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        domain = item.get("domain") or ".bilibili.com"
        cookies.append(
            {
                "name": str(name),
                "value": str(value),
                "domain": str(domain),
                "path": item.get("path") or "/",
                "httpOnly": bool(item.get("http_only", item.get("httpOnly", False))),
                "secure": bool(item.get("secure", True)),
                "sameSite": "Lax",
            }
        )
    if not cookies:
        raise ValueError("B站 cookie 为空，请重新登录")
    return {"cookies": cookies, "origins": []}


async def open_creator_center_async(account_id: int) -> dict:
    """启动有头浏览器并打开对应平台创作者中心，直到用户关闭浏览器。"""
    account = load_account(account_id)
    platform_type = account["type"]
    url = get_creator_url(platform_type)
    if not url:
        raise ValueError(f"不支持的平台类型: {platform_type}")

    cookie_file = cookie_path(account["filePath"])
    label = PLATFORM_LABELS.get(platform_type, "未知平台")
    print(f"🌐 打开创作者中心: {label} / {account['userName']} -> {url}")

    options = get_browser_options()
    options["headless"] = False  # 创作者中心必须可见

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**options)
        try:
            if platform_type == 6:
                storage = _bilibili_storage_state(cookie_file)
                context = await browser.new_context(storage_state=storage)
            else:
                context = await browser.new_context(storage_state=str(cookie_file))
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            disconnected = asyncio.Event()

            def _on_disconnected():
                disconnected.set()

            browser.on("disconnected", _on_disconnected)
            await disconnected.wait()
        finally:
            try:
                if browser.is_connected():
                    await browser.close()
            except Exception:
                pass

    return {
        "accountId": account_id,
        "platform": label,
        "userName": account["userName"],
        "url": url,
    }


def open_creator_center_in_thread(account_id: int) -> None:
    """在独立线程中运行，避免阻塞 Flask。"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(open_creator_center_async(account_id))
        loop.close()
    except Exception as exc:
        print(f"❌ 打开创作者中心失败 id={account_id}: {exc}")
        import traceback

        traceback.print_exc()
