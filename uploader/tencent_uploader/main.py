# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import os
from datetime import datetime
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import BASE_DIR, DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.log import tencent_logger

TENCENT_LOGIN_URL = "https://channels.weixin.qq.com"
TENCENT_UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
TENCENT_MANAGE_URL = "https://channels.weixin.qq.com/platform/post/list"
TENCENT_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
TENCENT_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _resolve_account_file(account_file: str | Path) -> str:
    path = Path(account_file).expanduser()
    if path.is_absolute():
        return str(path)

    if len(path.parts) == 1:
        return str((Path(BASE_DIR) / "cookies" / "tencent_uploader" / path).resolve())

    return str(path.resolve())


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(
    success: bool,
    status: str,
    message: str,
    account_file: str,
    qrcode: dict | None = None,
    current_url: str = "",
) -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


def _build_launch_kwargs(headless: bool) -> dict:
    launch_kwargs = {"headless": headless}
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_kwargs["channel"] = "chrome"
    return launch_kwargs


def _get_qrcode_utils():
    from utils.login_qrcode import build_login_qrcode_path
    from utils.login_qrcode import decode_qrcode_from_path
    from utils.login_qrcode import print_terminal_qrcode
    from utils.login_qrcode import remove_qrcode_file
    from utils.login_qrcode import save_data_url_image

    return {
        "build_login_qrcode_path": build_login_qrcode_path,
        "decode_qrcode_from_path": decode_qrcode_from_path,
        "print_terminal_qrcode": print_terminal_qrcode,
        "remove_qrcode_file": remove_qrcode_file,
        "save_data_url_image": save_data_url_image,
    }


def format_str_for_short_title(origin_title: str) -> str:
    if not origin_title or not str(origin_title).strip():
        return ""

    allowed_special_chars = "《》“”:+?%°"
    filtered_chars = [char if char.isalnum() or char in allowed_special_chars else " " if char == "," else "" for char in origin_title]
    formatted_string = "".join(filtered_chars).strip()

    if not formatted_string:
        return ""

    if len(formatted_string) > 16:
        formatted_string = formatted_string[:16]
    elif len(formatted_string) < 6:
        formatted_string += " " * (6 - len(formatted_string))

    return formatted_string


async def cookie_auth(account_file):
    account_file = _resolve_account_file(account_file)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=True))
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(TENCENT_UPLOAD_URL)
            await page.wait_for_url(TENCENT_UPLOAD_URL, timeout=5000)

            login_markers = [
                page.get_by_text("扫码登录", exact=True).first,
                page.get_by_text("发表视频", exact=True).first,
                page.get_by_role("button", name="发表").first,
            ]

            if await login_markers[0].count():
                tencent_logger.info(_msg("🥹", "cookie 已失效，得重新登录一下"))
                return False

            tencent_logger.success(_msg("🥳", "cookie 有效"))
            return True
        except Exception as exc:
            tencent_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            await browser.close()


async def _extract_tencent_qrcode_src(page: Page) -> str:
    if hasattr(page, "frame_locator"):
        try:
            iframe_locator = page.frame_locator('[src*="login-for-iframe"]')
            qr_code_img = iframe_locator.locator('div#app img.qrcode').first
            await qr_code_img.wait_for(state="visible", timeout=30000)
            src = await qr_code_img.get_attribute("src")
            if src and src.startswith("data:image/"):
                return src
        except Exception:
            pass

    selector_candidates = [
        "div.login-qrcode-wrap img.qrcode",
        "div.qrcode-wrap img.qrcode",
        "img.qrcode",
        'img[src^="data:image/"]',
    ]
    for selector in selector_candidates:
        qr_code_img = page.locator(selector).first
        try:
            if not await qr_code_img.count() or not await qr_code_img.is_visible():
                continue
            src = await qr_code_img.get_attribute("src")
            if src and src.startswith("data:image/"):
                return src
        except Exception:
            continue

    raise RuntimeError("未获取到视频号登录二维码地址")


async def _save_tencent_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    qrcode_utils = _get_qrcode_utils()
    qrcode_src = await _extract_tencent_qrcode_src(page)
    qrcode_path = qrcode_utils["save_data_url_image"](
        qrcode_src,
        qrcode_utils["build_login_qrcode_path"](account_file, suffix="tencent_login_qrcode"),
    )
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if qrcode_utils["remove_qrcode_file"](previous_qrcode_path):
            tencent_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))

    tencent_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = qrcode_utils["decode_qrcode_from_path"](qrcode_path)
    if qrcode_content:
        qrcode_utils["print_terminal_qrcode"](qrcode_content, qrcode_path, "微信")
    else:
        tencent_logger.warning(
            _msg(
                "😵",
                f"没能从二维码图片里解析出可打印内容，所以这次没法在终端重绘二维码；请直接打开 {qrcode_path} 扫码",
            )
        )

    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_tencent_login_completed(page: Page) -> bool:
    publish_markers = [
        page.locator('div:has-text("发表视频")').first,
        page.locator('button:has-text("发表")').first,
        page.locator('button:has-text("保存草稿")').first,
    ]
    for marker in publish_markers:
        try:
            if await marker.count() and await marker.is_visible():
                return True
        except Exception:
            continue

    if not (page.url.startswith(TENCENT_UPLOAD_URL) or page.url.startswith(TENCENT_MANAGE_URL)):
        return False

    login_markers = [
        page.locator("div.login-qrcode-wrap").first,
        page.locator("div.qrcode-wrap").first,
        page.locator("img.qrcode").first,
        page.locator('span:has-text("微信扫码登录 视频号助手")').first,
    ]
    for marker in login_markers:
        try:
            if await marker.count() and await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _is_tencent_qrcode_expired(page: Page) -> bool:
    tip_selectors = [
        'div.mask.show p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'div.mask.show p.refresh-tip:has-text("网络不可用，点击刷新")',
        'p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'p.refresh-tip:has-text("网络不可用，点击刷新")',
    ]
    for selector in tip_selectors:
        tip = page.locator(selector).first
        try:
            if await tip.count() and await tip.is_visible():
                return True
        except Exception:
            continue
    return False


async def _is_tencent_qrcode_scanned(page: Page) -> bool:
    scanned_tips = [
        'div.qr-tip div:has-text("已扫码")',
        'div.qr-tip div:has-text("需在手机上进行确认")',
    ]
    for selector in scanned_tips:
        tip = page.locator(selector).first
        try:
            if await tip.count() and await tip.is_visible():
                return True
        except Exception:
            continue
    return False


async def _refresh_tencent_qrcode(page: Page) -> None:
    visible_refresh_selectors = [
        "div.login-qrcode-wrap div.mask.show div.refresh-wrap",
        "div.login-qrcode-wrap div.mask.show .refresh-wrap",
    ]
    for selector in visible_refresh_selectors:
        refresh_wrap = page.locator(selector).first
        try:
            if not await refresh_wrap.count() or not await refresh_wrap.is_visible():
                continue
            await refresh_wrap.click()
            return
        except Exception:
            continue

    tip_selectors = [
        'div.mask.show p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'div.mask.show p.refresh-tip:has-text("网络不可用，点击刷新")',
        'p.refresh-tip:has-text("二维码已过期，点击刷新")',
        'p.refresh-tip:has-text("网络不可用，点击刷新")',
    ]
    for selector in tip_selectors:
        tip = page.locator(selector).first
        try:
            if not await tip.count() or not await tip.is_visible():
                continue
            refresh_wrap = tip.locator("xpath=ancestor::div[contains(@class, 'refresh-wrap')]").first
            if await refresh_wrap.count():
                await refresh_wrap.click()
            else:
                await tip.click()
            return
        except Exception:
            continue

    fallback_refresh = page.locator("div.login-qrcode-wrap div.refresh-wrap").first
    if await fallback_refresh.count():
        await fallback_refresh.click()
        return

    raise RuntimeError("未找到可点击的视频号二维码刷新区域")


async def _wait_for_tencent_login(
    page: Page,
    account_file: str,
    qrcode_info: dict,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
) -> dict:
    qrcode_path = Path(qrcode_info["image_path"])
    scanned_logged = False
    for _ in range(max_checks):
        if await _is_tencent_login_completed(page):
            tencent_logger.info(_msg("🥳", f"扫码成功，已经跳转到登录后页面: {page.url}"))
            return _build_login_result(True, "success", "视频号扫码登录成功", account_file, qrcode_info, page.url)

        if not scanned_logged and await _is_tencent_qrcode_scanned(page):
            tencent_logger.info(_msg("📱", "已经扫码啦，还差手机端确认一下"))
            scanned_logged = True

        if await _is_tencent_qrcode_expired(page):
            tencent_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
            await _refresh_tencent_qrcode(page)
            await asyncio.sleep(1)
            qrcode_info = await _save_tencent_qrcode(
                page,
                account_file,
                previous_qrcode_path=qrcode_path,
                qrcode_callback=qrcode_callback,
            )
            qrcode_path = Path(qrcode_info["image_path"])

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待视频号扫码登录超时", account_file, qrcode_info, page.url)


async def tencent_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    account_file = _resolve_account_file(account_file)
    Path(account_file).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context()
        qrcode_path = None
        result = _build_login_result(False, "failed", "视频号登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto(TENCENT_LOGIN_URL)
            qrcode_info = await _save_tencent_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            tencent_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_tencent_login(
                page,
                account_file,
                qrcode_info,
                qrcode_callback=qrcode_callback,
                poll_interval=poll_interval,
                max_checks=max_checks,
            )
            if result["success"]:
                await asyncio.sleep(2)
                await context.storage_state(path=account_file)
                if not await cookie_auth(account_file):
                    result = _build_login_result(
                        False,
                        "cookie_invalid",
                        "视频号扫码流程结束，但 cookie 校验失败",
                        account_file,
                        qrcode_info,
                        page.url,
                    )
            return result
        except Exception as exc:
            result = _build_login_result(
                False,
                "failed",
                str(exc),
                account_file,
                current_url=page.url if "page" in locals() else "",
            )
            return result
        finally:
            qrcode_utils = _get_qrcode_utils()
            if qrcode_utils["remove_qrcode_file"](qrcode_path):
                tencent_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                tencent_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()


async def tencent_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    account_file = _resolve_account_file(account_file)
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False

        tencent_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await tencent_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def get_tencent_cookie(account_file, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    return await tencent_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)


async def weixin_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    return await tencent_setup(
        account_file,
        handle=handle,
        return_detail=return_detail,
        qrcode_callback=qrcode_callback,
        headless=headless,
    )


class TencentBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = _resolve_account_file(account_file)
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成视频号登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成视频号登录: {self.account_file}")
        if self.publish_strategy not in {TENCENT_PUBLISH_STRATEGY_IMMEDIATE, TENCENT_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time_tencent(self, page: Page, publish_date: datetime):
        tencent_logger.info(
            _msg("🕒", f"小人准备设置定时发布: {publish_date.strftime('%Y-%m-%d %H:%M')}")
        )

        # 新版 UI：立即发布 / 定时发布 切换；旧版：label「定时」
        toggled = False
        for candidate in (
            page.get_by_text("定时发布", exact=True).last,
            page.locator("label").filter(has_text="定时发布").first,
            page.locator("label").filter(has_text="定时").nth(1),
        ):
            try:
                if await candidate.count() and await candidate.is_visible():
                    await candidate.scroll_into_view_if_needed()
                    await candidate.click(timeout=4000)
                    toggled = True
                    break
            except Exception:
                continue
        if not toggled:
            raise RuntimeError("未能切换到视频号「定时发布」")

        await page.wait_for_timeout(500)

        date_input = page.locator('input[placeholder="请选择发表时间"]').first
        if not await date_input.count():
            date_input = page.locator('input[placeholder*="发表时间"]').first
        await date_input.click()

        current_month = publish_date.strftime("%m月")
        page_month = await page.inner_text('span.weui-desktop-picker__panel__label:has-text("月")')
        if page_month != current_month:
            await page.click("button.weui-desktop-btn__icon__right")

        elements = await page.query_selector_all("table.weui-desktop-picker__table a")
        day_clicked = False
        for element in elements:
            if "weui-desktop-picker__disabled" in await element.evaluate("el => el.className"):
                continue
            text = await element.inner_text()
            if text.strip() == str(publish_date.day):
                await element.click()
                day_clicked = True
                break
        if not day_clicked:
            raise RuntimeError(f"未能选择定时发布日期: {publish_date.day}日")

        time_input = page.locator('input[placeholder="请选择时间"]').first
        if not await time_input.count():
            time_input = page.locator('input[placeholder*="时间"]').first
        await time_input.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(publish_date.strftime("%H:%M"))
        # 点一下编辑区收起时间面板
        editor = page.locator("div.input-editor").first
        if await editor.count():
            await editor.click()
        tencent_logger.success(
            _msg("🥳", f"定时发布时间已设置: {publish_date.strftime('%Y-%m-%d %H:%M')}")
        )

    async def open_upload_page(self, page: Page) -> None:
        await page.goto(TENCENT_UPLOAD_URL)
        await page.wait_for_url(TENCENT_UPLOAD_URL)

    async def upload_video_file(self, page: Page, file_path: str) -> None:
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(file_path)

    async def set_short_title(self, page: Page, title: str, short_title: str | None = None) -> None:
        # 未填标题且未显式传短标题时，不要自动填空格（平台短标题保持空白）
        if short_title is None:
            value = format_str_for_short_title(title or "")
        else:
            value = str(short_title)
        if not value.strip():
            tencent_logger.info(_msg("🧾", "标题为空，跳过填写短标题"))
            return

        short_title_element = (
            page.get_by_text("短标题", exact=True)
            .locator("..")
            .locator("xpath=following-sibling::div")
            .locator('span input[type="text"]')
        )
        if await short_title_element.count():
            await short_title_element.fill(value)

    async def fill_title_and_tags(self, page: Page) -> None:
        await page.locator("div.input-editor").click()
        title_text = (self.title or "").strip()
        if title_text:
            await page.keyboard.type(title_text)
            await page.keyboard.press("Enter")
        for tag in self.tags:
            await page.keyboard.type("#" + tag)
            await page.keyboard.press("Space")
        tencent_logger.info(_msg("🏷️", f"成功添加 hashtag: {len(self.tags)}"))

    async def fill_description(self, page: Page) -> None:
        await page.keyboard.press("Enter")
        await page.keyboard.type(self.desc)
        tencent_logger.info(_msg("🏷️", f"成功添加 desc: {len(self.desc)}"))

    async def apply_collection(self, page: Page) -> None:
        # 不自动选择合集，保持平台默认「选择合集」
        return

    async def apply_original_statement(self, page: Page) -> None:
        original_set = False
        if await page.get_by_label("视频为原创").count():
            await page.get_by_label("视频为原创").check()
            original_set = True

        try:
            label_locator = await page.locator('label:has-text("我已阅读并同意 《视频号原创声明使用条款》")').is_visible()
        except Exception:
            label_locator = False

        if label_locator:
            await page.get_by_label("我已阅读并同意 《视频号原创声明使用条款》").check()
            await page.get_by_role("button", name="声明原创").click()
            original_set = True

        declaration_entry = page.locator(
            'div.label span:has-text("声明原创"), '
            'div:has-text("声明原创"):has(input.ant-checkbox-input), '
            'div:has-text("原创声明"):has(input.ant-checkbox-input)'
        ).first
        if await declaration_entry.count():
            original_checkbox = page.locator("div.declare-original-checkbox input.ant-checkbox-input").first
            if await original_checkbox.count() and not await original_checkbox.is_disabled():
                await original_checkbox.click()
                await page.wait_for_timeout(500)
                checked_locator = page.locator(
                    "div.declare-original-dialog "
                    "label.ant-checkbox-wrapper.ant-checkbox-wrapper-checked:visible"
                )
                if not await checked_locator.count():
                    await page.locator("div.declare-original-dialog input.ant-checkbox-input:visible").first.click()

            original_type_form = page.locator('div.original-type-form > div.form-label:has-text("原创类型"):visible')
            if await original_type_form.count():
                category = getattr(self, "category", None)
                await page.locator("div.form-content:visible").click()
                option = None
                if category:
                    option = page.locator(
                        "ul.weui-desktop-dropdown__list "
                        f'li.weui-desktop-dropdown__list-ele:has-text("{category}")'
                    ).first
                    if not await option.count():
                        option = None
                if option is None:
                    option = page.locator(
                        "ul.weui-desktop-dropdown__list "
                        "li.weui-desktop-dropdown__list-ele:visible"
                    ).first
                if await option.count():
                    await option.click()
                await page.wait_for_timeout(1000)

            declare_button = page.locator('button:has-text("声明原创"):visible')
            if await declare_button.count():
                await declare_button.first.click()
                original_set = True
                await page.wait_for_timeout(1000)

        if not original_set:
            for original_text in ("声明原创", "原创声明", "视频为原创"):
                try:
                    modern_original = page.locator(f'text="{original_text}"').first
                    if await modern_original.count() and await modern_original.is_visible():
                        await modern_original.click()
                        original_set = True
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue

        content_declaration = page.locator('text="内容声明"').first
        try:
            if await content_declaration.count() and await content_declaration.is_visible():
                await content_declaration.click()
                for option_text in ("无需声明", "不声明", "无"):
                    option = page.locator(f'text="{option_text}"').first
                    if await option.count() and await option.is_visible():
                        await option.click()
                        tencent_logger.info(_msg("🧾", f"内容声明已选择: {option_text}"))
                        break
            else:
                tencent_logger.info(_msg("🧾", "当前页面未发现内容声明字段"))
        except Exception as exc:
            tencent_logger.warning(_msg("😵", f"内容声明设置失败，继续前先人工确认页面: {exc}"))

        if not original_set:
            try:
                diagnostic_path = Path(BASE_DIR) / "debug_tencent_original_missing.png"
                await page.screenshot(path=str(diagnostic_path), full_page=True)
                visible_text = (await page.locator("body").inner_text())[-4000:]
                tencent_logger.warning(_msg("😵", f"未确认声明原创，诊断截图: {diagnostic_path}"))
                tencent_logger.warning(_msg("🧾", f"页面末尾文本: {visible_text}"))
            except Exception as exc:
                tencent_logger.warning(_msg("😵", f"生成原创声明诊断信息失败: {exc}"))
            raise RuntimeError("未能在视频号发布页找到并设置“声明原创”，已停止发布")

    async def wait_for_upload_complete(self, page: Page) -> None:
        max_retries = 120
        retry_count = 0
        while retry_count < max_retries:
            retry_count += 1
            try:
                publish_button = page.get_by_role("button", name="发表")
                button_class = await publish_button.get_attribute("class")
                if button_class and "weui-desktop-btn_disabled" not in button_class:
                    tencent_logger.info(_msg("🥳", "视频上传完毕"))
                    break

                if retry_count % 5 == 0:
                    tencent_logger.info(_msg("🏃", f"正在上传视频中...（第{retry_count}次）"))
                await asyncio.sleep(2)

                upload_failed = await page.locator("div.status-msg.error").count()
                delete_button = await page.locator('div.media-status-content div.tag-inner:has-text("删除")').count()
                if upload_failed and delete_button:
                    tencent_logger.error(_msg("😵", "发现上传出错了，准备重试"))
                    await self.handle_upload_error(page)
            except Exception:
                if retry_count % 5 == 0:
                    tencent_logger.info(_msg("🏃", f"正在上传视频中...（第{retry_count}次）"))
                await asyncio.sleep(2)
        else:
            tencent_logger.warning(_msg("⚠️", f"上传等待超时：{max_retries}次尝试后仍未完成"))

    async def submit_publish(self, page: Page) -> None:
        max_publish_retries = 600
        publish_retry_count = 0
        verification_waited = False
        while publish_retry_count < max_publish_retries:
            publish_retry_count += 1
            try:
                # 检测验证码弹窗
                if not verification_waited:
                    verification_indicators = ['text="获取验证码"', 'text="请输入验证码"', 'text="安全验证"',
                                               'text="请完成验证"', '[class*="captcha"]', '[class*="verify"]']
                    has_verification = False
                    for selector in verification_indicators:
                        try:
                            if await page.locator(selector).count() > 0:
                                has_verification = True
                                break
                        except Exception:
                            continue
                    if has_verification:
                        tencent_logger.warning(_msg("⚠️", "检测到验证弹窗！请在浏览器窗口中手动完成验证..."))
                        tencent_logger.info(_msg("⏳", "等待手动验证完成（最多180秒）..."))
                        for wait_i in range(360):
                            await asyncio.sleep(0.5)
                            still_has = False
                            for selector in verification_indicators:
                                try:
                                    if await page.locator(selector).count() > 0:
                                        still_has = True
                                        break
                                except Exception:
                                    continue
                            if not still_has:
                                tencent_logger.success(_msg("✅", "验证已完成，继续发布流程"))
                                verification_waited = True
                                break
                            if wait_i % 20 == 0 and wait_i > 0:
                                tencent_logger.info(_msg("⏳", f"仍在等待验证完成...已等待{wait_i // 2}秒"))
                        else:
                            verification_waited = True

                if getattr(self, "is_draft", False):
                    draft_button = page.get_by_role("button", name="保存草稿")
                    if await draft_button.count():
                        await draft_button.click()
                    await page.wait_for_url("**/post/list**", timeout=5000)
                    tencent_logger.success(_msg("🥳", "视频草稿保存成功"))
                else:
                    publish_button = page.get_by_role("button", name="发表")
                    if await publish_button.count():
                        await publish_button.click()
                    await page.wait_for_url(TENCENT_MANAGE_URL, timeout=5000)
                    tencent_logger.success(_msg("🥳", "视频发布成功"))
                break
            except Exception as exc:
                current_url = page.url
                if getattr(self, "is_draft", False):
                    if "post/list" in current_url or "draft" in current_url:
                        tencent_logger.success(_msg("🥳", "视频草稿保存成功"))
                        break
                else:
                    if TENCENT_MANAGE_URL in current_url:
                        tencent_logger.success(_msg("🥳", "视频发布成功"))
                        break
                if publish_retry_count % 10 == 0:
                    tencent_logger.info(_msg("🏃", f"视频正在发布中...（第{publish_retry_count}次）"))
                if self.debug and publish_retry_count <= 5:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)
        else:
            tencent_logger.error(_msg("❌", f"发布超时：{max_publish_retries}次尝试后仍未成功"))
            raise RuntimeError(f"发布超时：{max_publish_retries}次尝试后仍未成功")


class TencentVideo(TencentBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        category=None,
        is_draft=False,
        desc: str | None = None,
        thumbnail_path: str | None = None,
        short_title: str | None = None,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        dry_run: bool = False,
        ai_generated: bool = False,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.category = category
        self.is_draft = is_draft
        self.desc = desc or ""
        self.thumbnail_path = thumbnail_path
        self.short_title = short_title
        self.dry_run = bool(dry_run)
        self.ai_generated = bool(ai_generated)

    async def validate_upload_args(self):
        await self.validate_base_args()
        self.title = "" if self.title is None else str(self.title)
        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def set_video_label(self, page: Page) -> bool:
        """将「视频标注」设为「含AI生成内容」。未勾选 / 找不到控件时不阻断发布。"""
        if not self.ai_generated:
            return False

        target_options = ("含AI生成内容", "含 AI 生成内容")
        target = target_options[0]
        tencent_logger.info(_msg("🧍", f"小人准备设置视频标注：{target}"))
        try:
            label = page.get_by_text("视频标注", exact=True).first
            try:
                await label.wait_for(state="visible", timeout=8000)
            except Exception:
                tencent_logger.info(_msg("🧾", "当前页面未发现「视频标注」字段，跳过"))
                return False

            await label.scroll_into_view_if_needed()
            await page.wait_for_timeout(200)

            # 已选中则跳过
            for text in target_options:
                already = page.get_by_text("视频标注", exact=True).locator(
                    "xpath=following-sibling::*[1]"
                ).get_by_text(text, exact=True).first
                try:
                    if await already.count() and await already.is_visible():
                        tencent_logger.info(_msg("🥳", f"视频标注已是「{text}」，跳过"))
                        return True
                except Exception:
                    pass

            # 打开下拉：优先点占位「选择视频标注」（发布页真实文案）
            trigger_candidates = [
                page.get_by_text("选择视频标注", exact=True).first,
                page.get_by_text("视频标注", exact=True)
                .locator("xpath=following-sibling::*[1]")
                .locator("text=选择视频标注")
                .first,
                page.get_by_text("视频标注", exact=True).locator("xpath=following-sibling::*[1]").first,
                page.locator(
                    "xpath=//*[normalize-space(text())='视频标注']/following::*[contains(normalize-space(.),'选择视频标注')][1]"
                ).first,
            ]
            opened = False
            for trigger in trigger_candidates:
                try:
                    if not await trigger.count():
                        continue
                    if not await trigger.is_visible():
                        continue
                    await trigger.scroll_into_view_if_needed()
                    await trigger.click(timeout=4000)
                    opened = True
                    tencent_logger.info(_msg("🖱️", "已点击视频标注下拉"))
                    break
                except Exception as exc:
                    tencent_logger.info(_msg("🧾", f"点击下拉候选失败: {exc}"))
                    continue

            if not opened:
                tencent_logger.warning(_msg("😵", "未能打开「视频标注」下拉"))
                await page.screenshot(
                    path=str(Path(BASE_DIR) / "debug_tencent_video_label_missing.png"),
                    full_page=True,
                )
                return False

            await page.wait_for_timeout(600)

            # 选项：对齐合集下拉（option-list-wrap）与 weui 下拉
            option = None
            for text in target_options:
                option_candidates = [
                    page.locator(".option-list-wrap").get_by_text(text, exact=True).first,
                    page.locator(
                        "ul.weui-desktop-dropdown__list "
                        f'li.weui-desktop-dropdown__list-ele:has-text("{text}")'
                    ).first,
                    page.locator('[class*="dropdown"]').get_by_text(text, exact=True).first,
                    page.get_by_role("option", name=text).first,
                    page.get_by_text(text, exact=True).first,
                ]
                for candidate in option_candidates:
                    try:
                        if not await candidate.count():
                            continue
                        await candidate.wait_for(state="visible", timeout=4000)
                        option = candidate
                        target = text
                        break
                    except Exception:
                        continue
                if option is not None:
                    break

            if option is None:
                tencent_logger.warning(_msg("😵", f"下拉已打开但未找到选项「{target_options[0]}」"))
                # 记录当前可见下拉文本，便于下次对齐选择器
                try:
                    visible_bits = await page.evaluate(
                        """() => {
                          const blocks = [];
                          for (const el of document.querySelectorAll(
                            '.option-list-wrap, ul.weui-desktop-dropdown__list, [class*="dropdown"], [role="listbox"], [role="menu"]'
                          )) {
                            const t = (el.innerText || '').trim();
                            if (t && (el.offsetWidth || el.offsetHeight)) {
                              blocks.push({cls: el.className, text: t.slice(0, 300)});
                            }
                          }
                          return blocks.slice(0, 10);
                        }"""
                    )
                    tencent_logger.info(_msg("🧾", f"可见下拉候选: {visible_bits}"))
                except Exception:
                    pass
                await page.screenshot(
                    path=str(Path(BASE_DIR) / "debug_tencent_video_label_missing.png"),
                    full_page=True,
                )
                return False

            await option.click(timeout=4000)
            await page.wait_for_timeout(500)

            # 校验：占位消失或出现目标文案
            for text in target_options:
                shown = page.get_by_text(text, exact=True).first
                try:
                    if await shown.count() and await shown.is_visible():
                        placeholder = page.get_by_text("选择视频标注", exact=True).first
                        if await placeholder.count() and await placeholder.is_visible():
                            continue
                        tencent_logger.success(_msg("🥳", f"视频标注已设置为「{text}」"))
                        return True
                except Exception:
                    continue

            # 点击成功但校验宽松通过（部分账号控件文案刷新慢）
            tencent_logger.success(_msg("🥳", f"已点击视频标注选项「{target}」"))
            return True
        except Exception as exc:
            tencent_logger.warning(_msg("😵", f"设置视频标注失败，继续发布: {exc}"))
            try:
                await page.screenshot(
                    path=str(Path(BASE_DIR) / "debug_tencent_video_label_missing.png"),
                    full_page=True,
                )
            except Exception:
                pass
            return False

    async def handle_upload_error(self, page: Page) -> None:
        tencent_logger.info(_msg("😵", "视频出错了，重新上传中"))
        await page.locator('div.media-status-content div.tag-inner:has-text("删除")').click()
        await page.get_by_role("button", name="删除", exact=True).click()
        await self.upload_video_file(page, self.file_path)

    async def set_thumbnail(self, page: Page) -> None:
        if not self.thumbnail_path:
            return

        tencent_logger.info(_msg("🖼️", "小人准备设置封面"))

        cover_entry_selectors = [
            'div.vertical-cover-wrap:has-text("个人主页卡片"):has-text("3:4")',
            'div.vertical-cover-wrap:has-text("3:4")',
            'div.vertical-cover-wrap:has-text("个人主页卡片")',
        ]
        for selector in cover_entry_selectors:
            cover_entry = page.locator(selector).first
            try:
                if not await cover_entry.count():
                    continue
                await cover_entry.wait_for(state="visible", timeout=3000)
                await cover_entry.click()
                await page.wait_for_timeout(500)
                break
            except Exception:
                continue

        cover_dialog = page.locator("div.weui-desktop-dialog").filter(has_text="编辑个人主页卡片").first
        if not await cover_dialog.count():
            tencent_logger.info(_msg("🧍", "当前页面没有出现封面编辑弹窗，小人先跳过自定义封面"))
            return

        try:
            await cover_dialog.wait_for(state="visible", timeout=5000)
        except Exception:
            tencent_logger.warning(_msg("😵", "封面编辑弹窗暂时不可见，这次先跳过自定义封面"))
            return

        file_input = cover_dialog.locator('.single-cover-uploader-wrap input[type="file"]').first
        await file_input.wait_for(state="attached", timeout=10000)
        await file_input.set_input_files(self.thumbnail_path)
        await page.wait_for_timeout(1000)

        crop_dialog = page.locator("div.weui-desktop-dialog").filter(has_text="裁剪封面图").first
        if await crop_dialog.count():
            try:
                await crop_dialog.wait_for(state="visible", timeout=10000)
                crop_confirm_button = crop_dialog.locator(
                    'div.weui-desktop-dialog__ft button.weui-desktop-btn_primary:has-text("确定")'
                ).first
                if await crop_confirm_button.count():
                    await crop_confirm_button.wait_for(state="visible", timeout=5000)
                    await crop_confirm_button.click()
                    await page.wait_for_timeout(1000)
            except Exception as exc:
                tencent_logger.warning(_msg("😵", f"封面裁剪确认时出错，小人继续尝试保存主弹窗: {exc}"))

        confirm_button = cover_dialog.locator(
            'div.weui-desktop-dialog__ft button.weui-desktop-btn_primary:has-text("确认")'
        ).first
        await confirm_button.wait_for(state="visible", timeout=10000)
        await confirm_button.click()
        tencent_logger.success(_msg("🥳", "封面已经设置完成"))

    async def prepare_video_for_publish(self, page: Page) -> None:
        await self.fill_title_and_tags(page)
        await self.fill_description(page)
        await self.apply_collection(page)

    async def upload(self, playwright: Playwright) -> None:
        tencent_logger.info(_msg("🧍", "小人先检查 cookie、视频文件和发布时间"))
        await self.validate_upload_args()
        tencent_logger.info(_msg("🥳", "上传前检查通过"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)

        try:
            page = await context.new_page()
            await self.open_upload_page(page)
            tencent_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}"))

            await self.upload_video_file(page, self.file_path)
            await self.prepare_video_for_publish(page)
            await self.wait_for_upload_complete(page)
            await self.apply_original_statement(page)
            await self.set_video_label(page)
            await self.set_thumbnail(page)

            if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
                await self.set_schedule_time_tencent(page, self.publish_date)

            await self.set_short_title(page, self.title, self.short_title)

            if getattr(self, "dry_run", False):
                tencent_logger.warning(_msg("🛑", "【仅预览不发布】已跳过点击发表按钮"))
                tencent_logger.info(_msg("👀", "请在浏览器窗口核对表单是否正确"))
                tencent_logger.info(_msg("⏳", "页面将保持打开约 120 秒后自动关闭"))
                try:
                    from pathlib import Path as _Path
                    await page.screenshot(full_page=True, path=str(_Path(self.account_file).with_name("dry_run_preview.png")))
                except Exception:
                    pass
                for i in range(120):
                    await asyncio.sleep(1)
                    if i > 0 and i % 30 == 0:
                        tencent_logger.info(_msg("⏳", f"预览中…还剩约 {120 - i} 秒自动关闭"))
                tencent_logger.info(_msg("🛑", "预览结束，关闭浏览器（未点击发表）"))
            else:
                await self.submit_publish(page)

            await context.storage_state(path=self.account_file)
            tencent_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()
            await browser.close()

    async def tencent_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.tencent_upload_video()


class TencentNote(TencentBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        is_draft: bool = False,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.image_paths = image_paths
        self.note = note or ""
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []
        self.is_draft = is_draft

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")
        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def switch_to_note_mode(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.switch_to_note_mode 中补充视频号切换到图文发布模式的逻辑")

    async def upload_note_images(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.upload_note_images 中补充视频号图文图片上传逻辑")

    async def fill_note_title_and_tags(self, page: Page) -> None:
        raise NotImplementedError("请在 TencentNote.fill_note_title_and_tags 中补充视频号图文标题/话题填写逻辑")

    async def fill_note_body(self, page: Page) -> None:
        return None

    async def prepare_note_for_publish(self, page: Page) -> None:
        await self.fill_note_title_and_tags(page)
        await self.fill_note_body(page)
        await self.apply_collection(page)
        await self.apply_original_statement(page)

    async def upload_note_content(self, page: Page) -> None:
        await self.switch_to_note_mode(page)
        await self.upload_note_images(page)
        await self.prepare_note_for_publish(page)

    async def upload(self, playwright: Playwright) -> None:
        tencent_logger.info(_msg("🧍", "小人先检查 cookie、图文图片和发布时间"))
        await self.validate_upload_args()
        tencent_logger.info(_msg("🥳", "图文上传前检查通过"))

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=self.headless))
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)

        try:
            page = await context.new_page()
            await self.open_upload_page(page)
            tencent_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))

            await self.upload_note_content(page)

            if self.publish_strategy == TENCENT_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
                await self.set_schedule_time_tencent(page, self.publish_date)

            await self.submit_publish(page)

            await context.storage_state(path=self.account_file)
            tencent_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()
            await browser.close()

    async def tencent_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.tencent_upload_note()
