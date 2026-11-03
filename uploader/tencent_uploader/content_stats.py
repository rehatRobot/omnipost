# uploader/tencent_uploader/content_stats.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright

from conf import LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script
from utils.log import tencent_logger

MANAGE_URL = "https://channels.weixin.qq.com/platform/post/list"
# 新版助手把作品列表挂在 micro/content 子路径下，接口仍可能返回 HTTP 201
POST_LIST_API = "https://channels.weixin.qq.com/micro/content/cgi-bin/mmfinderassistant-bin/post/post_list"

TENCENT_LIST_URL_HINTS = (
    "mmfinderassistant-bin/post/post_list",
    "micro/content/cgi-bin/mmfinderassistant-bin/post/post_list",
    "post/post_list",
    "mmfinderassistant-bin/statistic/post_list",
    "statistic/post_list",
)


class TencentStatsSyncError(Exception):
    def __init__(self, message: str, code: int = 500):
        super().__init__(message)
        self.code = code
        self.message = message


def is_tencent_list_api_url(url: str) -> bool:
    u = (url or "").lower()
    return any(hint in u for hint in TENCENT_LIST_URL_HINTS)


def normalize_count(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        try:
            if s.endswith("万"):
                return int(float(s[:-1]) * 10000)
            return int(float(s))
        except (TypeError, ValueError):
            return 0
    return 0


def _extract_list(payload: dict) -> list:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("list", "feeds", "postList", "post_list", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            return _extract_list({"data": nested})
    for key in ("list", "feeds", "postList", "post_list", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def merge_intercepted_payloads(payloads: list[dict]) -> list[dict]:
    """Merge post_list / statistic payloads by objectId, last fields win on overlap."""
    merged: dict[str, dict] = {}
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for raw in _extract_list(payload):
            if not isinstance(raw, dict):
                continue
            oid = str(raw.get("objectId") or raw.get("exportId") or raw.get("id") or "").strip()
            if not oid:
                continue
            if oid in merged:
                merged[oid].update(raw)
            else:
                merged[oid] = dict(raw)
    return list(merged.values())


def _item_sort_ts(raw: dict) -> int:
    ts = raw.get("createTime") or raw.get("createtime") or raw.get("create_time") or raw.get("postTime") or 0
    try:
        ts_i = int(ts)
        if ts_i > 10_000_000_000:
            ts_i //= 1000
        return ts_i
    except (TypeError, ValueError):
        return 0


def _published_at(raw: dict) -> str:
    ts = _item_sort_ts(raw)
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(raw.get("createTime") or "")


def _desc_obj(raw: dict) -> dict:
    desc = raw.get("objectDesc") or raw.get("desc") or {}
    return desc if isinstance(desc, dict) else {}


def _cover_url(raw: dict) -> str:
    desc = _desc_obj(raw)
    media = desc.get("media") or raw.get("media") or []
    if isinstance(media, list) and media:
        first = media[0]
        if isinstance(first, dict):
            return str(
                first.get("coverUrl")
                or first.get("fullCoverUrl")
                or first.get("thumbUrl")
                or first.get("url")
                or ""
            )
    return str(raw.get("coverUrl") or raw.get("cover") or "")


def _title(raw: dict) -> str:
    desc = _desc_obj(raw)
    title = desc.get("description") or raw.get("description") or raw.get("title") or raw.get("desc")
    if isinstance(title, dict):
        title = title.get("description") or title.get("title") or ""
    return str(title or "").strip()


def _status_text(raw: dict) -> str:
    status = raw.get("status")
    mapping = {
        0: "草稿",
        1: "已发布",
        2: "审核中",
        3: "未通过",
        4: "已删除",
        5: "定时发布",
    }
    try:
        status_i = int(status)
    except (TypeError, ValueError):
        status_i = None
    if status_i in mapping:
        return mapping[status_i]
    flag = raw.get("visibleFlag")
    if flag in (1, True, "1"):
        return "已发布"
    if isinstance(raw.get("statusDesc"), str) and raw["statusDesc"].strip():
        return raw["statusDesc"].strip()
    return "已发布"


def parse_tencent_item(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    item_id = raw.get("objectId") or raw.get("exportId") or raw.get("id")
    if item_id is None or str(item_id).strip() == "":
        return None
    return {
        "item_id": str(item_id),
        "title": _title(raw),
        "cover_url": _cover_url(raw),
        "status": _status_text(raw),
        "published_at": _published_at(raw),
        "play_count": normalize_count(
            raw.get("readCount", raw.get("playCount", raw.get("viewCount", 0)))
        ),
        "like_count": normalize_count(raw.get("likeCount", raw.get("like_count", 0))),
        "comment_count": normalize_count(raw.get("commentCount", raw.get("comment_count", 0))),
        "share_count": normalize_count(
            raw.get("forwardCount", raw.get("shareCount", raw.get("share_count", 0)))
        ),
        "collect_count": normalize_count(
            raw.get("favCount", raw.get("collectCount", raw.get("collect_count", 0)))
        ),
        "raw_json": json.dumps(raw, ensure_ascii=False)[:8000],
    }


def parse_tencent_list_payload(payload: dict | list[dict], limit: int = 5) -> list[dict]:
    limit = max(0, int(limit))
    if isinstance(payload, list):
        raw_items = [raw for raw in payload if isinstance(raw, dict)]
    else:
        raw_items = merge_intercepted_payloads([payload] if isinstance(payload, dict) else [])
    raw_items.sort(key=_item_sort_ts, reverse=True)
    items: list[dict] = []
    for raw in raw_items:
        parsed = parse_tencent_item(raw)
        if parsed:
            items.append(parsed)
        if len(items) >= limit:
            break
    return items


def _payload_looks_ok(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    err = payload.get("errCode", payload.get("code"))
    if err not in (None, 0, "0"):
        return False
    return True


def _ok_http_status(status: int) -> bool:
    # 视频号助手多数 cgi 返回 201 Created，而不是 200
    return 200 <= int(status) < 300


async def _safe_text_count(page, text: str) -> int:
    try:
        return await page.get_by_text(text).count()
    except Exception:
        return 0


async def _ensure_post_list_page(page) -> None:
    """作品管理页可能被 SPA 重定向到 /platform，尽量点回内容管理。"""
    url = (page.url or "").lower()
    if "/platform/post/list" in url:
        return
    for label in ("内容管理", "视频", "视频图文"):
        try:
            loc = page.get_by_text(label, exact=False).first
            if await loc.count():
                await loc.click(timeout=3000)
                await page.wait_for_timeout(800)
                if "/platform/post/list" in (page.url or "").lower():
                    return
        except Exception:
            continue
    try:
        await page.goto(MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass


async def _fetch_post_list_in_page(page, page_size: int = 20) -> dict | None:
    """拦截失败时主动 POST post_list（携带页面登录态）。"""
    try:
        fetched = await page.evaluate(
            """async ({ apiUrl, pageSize }) => {
                const resp = await fetch(apiUrl, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        currentPage: 1,
                        pageSize,
                        timestamp: Date.now(),
                        _log_finder_uin: '',
                        _log_finder_id: '',
                        rawKeyBuff: null,
                        pluginSessionId: null,
                        scene: 7,
                        reqScene: 7,
                    }),
                });
                if (!(resp.status >= 200 && resp.status < 300)) {
                    return { __http_status: resp.status };
                }
                return await resp.json();
            }""",
            {"apiUrl": POST_LIST_API, "pageSize": max(int(page_size), 5)},
        )
        if isinstance(fetched, dict) and not fetched.get("__http_status"):
            return fetched
        tencent_logger.warning("主动请求 post_list 失败: %s", fetched)
    except Exception as exc:
        tencent_logger.warning("主动请求 post_list 异常: %s", exc)
    return None


async def sync_recent_items(account_file: str | Path, limit: int = 5, headless: bool | None = None) -> list[dict]:
    account_file = Path(account_file)
    if not account_file.exists():
        raise TencentStatsSyncError("cookie 文件不存在，请先在账号管理中登录视频号", code=401)

    headless = LOCAL_CHROME_HEADLESS if headless is None else headless
    payloads: list[dict] = []
    api_seen: list[str] = []

    async with async_playwright() as playwright:
        launch_args = {"headless": headless}
        if LOCAL_CHROME_PATH:
            launch_args["executable_path"] = LOCAL_CHROME_PATH
        else:
            launch_args["channel"] = "chrome"
        browser = await playwright.chromium.launch(**launch_args)
        try:
            context = await browser.new_context(storage_state=str(account_file))
            context = await set_init_script(context)
            page = await context.new_page()

            async def on_response(response):
                try:
                    url = response.url or ""
                    if "mmfinderassistant-bin" in url and len(api_seen) < 60:
                        path = url.split("?")[0]
                        short = path.split("mmfinderassistant-bin")[-1] if "mmfinderassistant-bin" in path else path
                        api_seen.append(f"{response.status} {short}")
                    if not is_tencent_list_api_url(url):
                        return
                    if not _ok_http_status(response.status):
                        return
                    data = await response.json()
                    if isinstance(data, dict):
                        payloads.append(data)
                except Exception as exc:
                    tencent_logger.debug("intercept response parse failed: %s", exc)
                    return

            page.on("response", on_response)
            await page.goto(MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
            await _ensure_post_list_page(page)

            for _ in range(50):
                url = (page.url or "").lower()
                if "login" in url:
                    raise TencentStatsSyncError("视频号 cookie 已失效，请重新登录", code=401)
                if await _safe_text_count(page, "微信扫码登录") or await _safe_text_count(page, "扫码登录"):
                    raise TencentStatsSyncError("视频号 cookie 已失效，请重新登录", code=401)
                if any(_extract_list(p) for p in payloads):
                    break
                if any(_payload_looks_ok(p) and isinstance(p.get("data"), dict) for p in payloads):
                    break
                await page.wait_for_timeout(500)
            else:
                await _ensure_post_list_page(page)
                await page.reload(wait_until="domcontentloaded", timeout=60000)
                for _ in range(25):
                    if any(_extract_list(p) for p in payloads) or any(_payload_looks_ok(p) for p in payloads):
                        break
                    await page.wait_for_timeout(500)

            await page.wait_for_timeout(800)

            if not payloads:
                fetched = await _fetch_post_list_in_page(page, page_size=max(limit * 4, 20))
                if fetched:
                    payloads.append(fetched)
                    tencent_logger.info("已通过主动请求 post_list 获取作品列表")

            if not payloads:
                tencent_logger.warning(
                    "tencent stats intercept miss final_url=%s api_seen=%s",
                    page.url,
                    api_seen[:40],
                )
                raise TencentStatsSyncError("未拦截到视频号作品列表接口，页面结构可能已变化", code=500)

            for payload in payloads:
                err = payload.get("errCode", payload.get("code"))
                if err not in (None, 0, "0") and not _extract_list(payload):
                    raise TencentStatsSyncError(
                        f"视频号作品列表返回异常: {payload.get('errMsg') or payload.get('msg') or err}",
                        code=500,
                    )

            raw_items = merge_intercepted_payloads(payloads)
            items = parse_tencent_list_payload(raw_items, limit=limit)
            tencent_logger.info(f"视频号作品同步完成: {len(items)} 条 (limit={limit})")
            return items
        finally:
            await browser.close()


def sync_recent_items_sync(account_file: str | Path, limit: int = 5, headless: bool | None = None) -> list[dict]:
    return asyncio.run(sync_recent_items(account_file, limit=limit, headless=headless))
