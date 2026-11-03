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

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.files_times import get_absolute_path
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import kuaishou_logger

KUAISHOU_UPLOAD_URL = "https://cp.kuaishou.com/article/publish/video"
KUAISHOU_MANAGE_URL = "https://cp.kuaishou.com/article/manage/video?status=2&from=publish"
KUAISHOU_LOGIN_URL = "https://passport.kuaishou.com/pc/account/login/?sid=kuaishou.web.cp.api&callback=https%3A%2F%2Fcp.kuaishou.com%2Frest%2Finfra%2Fsts%3FfollowUrl%3Dhttps%253A%252F%252Fcp.kuaishou.com%252Farticle%252Fpublish%252Fvideo%26setRootDomain%3Dtrue"
KUAISHOU_UPLOAD_URL_PATTERN = "**/article/publish/video**"
KUAISHOU_MANAGE_URL_PATTERN = "**/article/manage/video?status=2&from=publish**"
KUAISHOU_COOKIE_INVALID_SELECTOR = "div.names div.container div.name:text('机构服务')"
KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
KUAISHOU_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _print_ks_qrcode(qrcode_content: str, qrcode_path: Path) -> None:
    try:
        print_terminal_qrcode(qrcode_content, qrcode_path, "快手APP", compact=False, border=2)
    except TypeError as exc:
        if "unexpected keyword argument 'compact'" not in str(exc):
            raise
        kuaishou_logger.warning(_msg("😵", "检测到旧版二维码打印函数，小人切回兼容模式继续登录"))
        print_terminal_qrcode(qrcode_content, qrcode_path, "快手APP")


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


async def _is_ks_cookie_invalid(page: Page, timeout: int = 5000) -> bool:
    try:
        await page.wait_for_selector(KUAISHOU_COOKIE_INVALID_SELECTOR, timeout=timeout)
        return True
    except Exception:
        return False


async def _extract_ks_qrcode_src(page: Page) -> str:
    login_form = page.locator("main#login-form").first
    await login_form.wait_for(state="visible", timeout=30000)

    qrcode_img = login_form.locator('div.qr-login img[alt="qrcode"]').first
    try:
        if not await qrcode_img.count() or not await qrcode_img.is_visible():
            platform_switch = login_form.locator("div.platform-switch").first
            await platform_switch.wait_for(state="visible", timeout=10000)
            await platform_switch.click()
            await asyncio.sleep(1)
    except Exception:
        platform_switch = login_form.locator("div.platform-switch").first
        await platform_switch.wait_for(state="visible", timeout=10000)
        await platform_switch.click()
        await asyncio.sleep(1)

    await qrcode_img.wait_for(state="visible", timeout=15000)

    qrcode_src = await qrcode_img.get_attribute("src")
    if not qrcode_src:
        raise RuntimeError("未获取到快手登录二维码地址")

    return qrcode_src


async def _save_ks_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    qrcode_src = await _extract_ks_qrcode_src(page)
    qrcode_path = save_data_url_image(qrcode_src, build_login_qrcode_path(account_file, suffix="ks_login_qrcode"))

    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            kuaishou_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))

    kuaishou_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        _print_ks_qrcode(qrcode_content, qrcode_path)
    else:
        kuaishou_logger.warning(_msg("😵", f"终端没法完整显示二维码，请打开 {qrcode_path} 扫码"))

    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_ks_qrcode_expired(page: Page) -> bool:
    expired_box = page.locator("div.qrcode-status.qrcode-status-timeout").first
    try:
        if not await expired_box.count():
            return False
        return await expired_box.is_visible()
    except Exception:
        return False


async def _is_ks_login_page_gone(page: Page) -> bool:
    try:
        login_form = page.locator("main#login-form").first
        if not await login_form.count():
            return True
        return not await login_form.is_visible()
    except Exception:
        return True


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(headless=True, executable_path=LOCAL_CHROME_PATH)
        else:
            browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto(KUAISHOU_UPLOAD_URL)
            if await _is_ks_cookie_invalid(page):
                kuaishou_logger.info(_msg("🥹", "cookie 已失效，得重新登录一下"))
                return False

            kuaishou_logger.success(_msg("🥳", "cookie 有效"))
            return True
        except Exception as exc:
            kuaishou_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            await browser.close()


async def ks_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    account_file = get_absolute_path(account_file, "ks_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        kuaishou_logger.info(_msg("🥹", "cookie 失效了，准备重新登录快手创作者平台"))
        result = await get_ks_cookie(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def get_ks_cookie(
    account_file,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
    poll_interval: int = 3,
    max_checks: int = 100,
):
    if headless:
        kuaishou_logger.info(_msg("🖼️", "快手登录将以无头模式运行，小人会输出终端二维码并保存本地二维码图片"))

    async with async_playwright() as playwright:
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(headless=headless, executable_path=LOCAL_CHROME_PATH)
        else:
            browser = await playwright.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context()
        context = await set_init_script(context)
        qrcode_path = None
        qrcode_info = None
        result = _build_login_result(False, "failed", "快手登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto(KUAISHOU_LOGIN_URL)
            kuaishou_logger.info(_msg("🧍", "请在浏览器里扫码登录快手，小人正在耐心等待"))

            qrcode_info = await _save_ks_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])

            for _ in range(max_checks):
                if page.url.startswith(KUAISHOU_UPLOAD_URL) or await _is_ks_login_page_gone(page):
                    await context.storage_state(path=account_file)
                    if await cookie_auth(account_file):
                        kuaishou_logger.success(_msg("🥳", "快手扫码登录成功，小人开心收工"))
                        result = _build_login_result(True, "success", "快手扫码登录成功", account_file, qrcode_info, page.url)
                    else:
                        kuaishou_logger.error(_msg("😢", "快手扫码完成了，但 cookie 校验失败"))
                        result = _build_login_result(
                            False,
                            "cookie_invalid",
                            "快手扫码流程结束，但 cookie 校验失败",
                            account_file,
                            qrcode_info,
                            page.url,
                        )
                    return result

                if qrcode_info and await _is_ks_qrcode_expired(page):
                    kuaishou_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
                    refresh_button = page.locator("p.qrcode-refresh").first
                    if await refresh_button.count():
                        await refresh_button.click()
                        await asyncio.sleep(1)
                    qrcode_info = await _save_ks_qrcode(
                        page,
                        account_file,
                        qrcode_path,
                        qrcode_callback=qrcode_callback,
                    )
                    qrcode_path = Path(qrcode_info["image_path"])

                await asyncio.sleep(poll_interval)

            result = _build_login_result(
                False,
                "timeout",
                "等待快手扫码登录超时",
                account_file,
                qrcode_info,
                page.url,
            )
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                kuaishou_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                kuaishou_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()

    return result


class KSBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str | None = None,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = str(account_file)
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.headless = headless
        self.local_executable_path = LOCAL_CHROME_PATH
        self.date_format = "%Y-%m-%d %H:%M"

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成快手登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成快手登录: {self.account_file}")

        if self.publish_strategy is None:
            self.publish_strategy = (
                KUAISHOU_PUBLISH_STRATEGY_SCHEDULED
                if self.publish_date != 0
                else KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE
            )

        if self.publish_strategy not in {
            KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE,
            KUAISHOU_PUBLISH_STRATEGY_SCHEDULED,
        }:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == KUAISHOU_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def set_schedule_time(self, page: Page, publish_date: datetime):
        kuaishou_logger.info(_msg("🕒", "小人准备设置定时发布时间"))
        publish_date_str = publish_date.strftime("%Y-%m-%d %H:%M:%S")

        # 1. 切换到"定时发布"radio (用文本匹配更稳)
        await page.locator('label.ant-radio-wrapper').filter(has_text="定时发布").click()
        await asyncio.sleep(2)

        # 2. 点击 picker 打开下拉面板
        await page.locator('input[placeholder="选择日期时间"]').click()
        await asyncio.sleep(1)

        # 3. 用 React 兼容的方式直接设置 input 的 value
        #    (ant-design DatePicker 是 controlled component, 必须用 native setter + bubbling event)
        js_code = """
        (newValue) => {
            const input = document.querySelector('input[placeholder="选择日期时间"]');
            if (!input) return false;
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeSetter.call(input, newValue);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        """
        ok = await page.evaluate(js_code, publish_date_str)
        if not ok:
            kuaishou_logger.error("❌ 找不到时间选择器输入框")
            return

        await asyncio.sleep(1)
        # 4. 按 Enter 确认
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        kuaishou_logger.info(f"✅ 定时发布时间已设置为 {publish_date_str}")

    async def close_guide_overlay(self, page: Page) -> bool:
        joyride_tooltip = page.locator('div[id^="react-joyride-step"] div[role="alertdialog"]')

        # 判断是否显示
        if await joyride_tooltip.count() > 0 and await joyride_tooltip.first.is_visible():
            print("检测到 Joyride 引导遮罩，正在关闭...")

            # 点击关闭按钮（X），使用多个可靠特征
            close_button = page.locator('div[role="alertdialog"]').locator(
                '[aria-label="Skip"], [data-action="skip"], button[title="Skip"]'
            )

            await close_button.click(force=True)

            # 等待遮罩消失
            await joyride_tooltip.wait_for(state="hidden", timeout=5000)

            print("✅ 已关闭 Joyride 遮罩")
        else:
            print("未检测到 Joyride 遮罩，继续执行")


    async def _focus_description_editor(self, page: Page) -> None:
        """聚焦描述编辑器并把光标移到末尾。"""
        desc_box = page.get_by_text("描述").locator("xpath=following-sibling::div").first
        if not await desc_box.count():
            return
        await desc_box.click()
        await page.wait_for_timeout(150)
        editable = desc_box.locator(
            '[contenteditable="true"], [role="textbox"], .DraftEditor-root, .public-DraftEditor-content'
        ).first
        try:
            if await editable.count() and await editable.is_visible():
                await editable.click()
                await page.wait_for_timeout(100)
        except Exception:
            pass
        for key in ("Control+End", "End"):
            try:
                await page.keyboard.press(key)
            except Exception:
                pass
        await page.wait_for_timeout(100)

    async def _paste_into_description(self, page: Page, text: str) -> None:
        """模拟手动复制粘贴（快手批量粘贴 #话题 可正确识别为标签）。"""
        try:
            await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass
        await page.evaluate(
            """async (t) => { await navigator.clipboard.writeText(t); }""",
            text,
        )
        await page.keyboard.press("Control+V")
        await page.wait_for_timeout(800)

    async def fill_tags(self, page: Page) -> None:
        """批量粘贴 #话题，与手动复制粘贴效果一致。"""
        tags = [str(t).strip().lstrip("#") for t in (self.tags or []) if str(t).strip()]
        if not tags:
            return

        # 快手最多 4 个话题（与前端 platformTopicCount 一致）
        tags = tags[:4]
        paste_text = " ".join(f"#{tag}" for tag in tags)
        kuaishou_logger.info(_msg("🏷️", f"小人准备批量粘贴话题: {paste_text}"))

        await self._focus_description_editor(page)
        await page.wait_for_timeout(400)
        # 描述已有内容时，先补一个空格再粘贴话题
        await page.keyboard.type(" ")
        await self._paste_into_description(page, paste_text)
        kuaishou_logger.success(_msg("🥳", f"已粘贴 {len(tags)} 个话题"))

    async def _dismiss_blocking_overlays(self, page: Page) -> None:
        """关闭可能挡住发布按钮的下拉/引导层。"""
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            await self.close_guide_overlay(page)
        except Exception:
            pass
        # 点击页面空白处收起 ant-select 下拉
        try:
            await page.mouse.click(8, 8)
            await page.wait_for_timeout(150)
        except Exception:
            pass

    async def _click_publish_button(self, page: Page) -> bool:
        """多策略点击「发布」，兼容 antd 按钮非标准 role 的情况。"""
        await self._dismiss_blocking_overlays(page)

        candidates = [
            page.get_by_role("button", name="发布", exact=True),
            page.get_by_role("button", name="发布"),
            page.locator('button:has-text("发布")').filter(has_not_text="定时").first,
            page.get_by_text("发布", exact=True),
            page.locator('button.ant-btn-primary:has-text("发布")').first,
            page.locator('[class*="publish"] button:has-text("发布"), [class*="footer"] button:has-text("发布")').first,
        ]

        for btn in candidates:
            try:
                if not await btn.count():
                    continue
                target = btn.first if hasattr(btn, "first") else btn
                # 优先点可见且启用的
                try:
                    if not await target.is_visible():
                        continue
                except Exception:
                    pass
                try:
                    disabled = await target.get_attribute("disabled")
                    aria_disabled = await target.get_attribute("aria-disabled")
                    cls = (await target.get_attribute("class")) or ""
                    if disabled is not None or aria_disabled == "true" or "disabled" in cls:
                        continue
                except Exception:
                    pass

                await target.scroll_into_view_if_needed()
                await page.wait_for_timeout(200)
                try:
                    await target.click(timeout=3000)
                except Exception:
                    await target.click(force=True, timeout=3000)
                kuaishou_logger.info(_msg("🖱️", "已点击「发布」按钮"))
                return True
            except Exception:
                continue

        # 最后用 JS 兜底：找页面底部主按钮
        try:
            clicked = await page.evaluate(
                """() => {
                    const texts = ['发布'];
                    const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, div, span'));
                    const match = buttons.find(el => {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (!texts.includes(t)) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 20 || rect.height < 16) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.pointerEvents === 'none') return false;
                        if (el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                        if ((el.className || '').includes('disabled')) return false;
                        return true;
                    });
                    if (!match) return false;
                    match.click();
                    return true;
                }"""
            )
            if clicked:
                kuaishou_logger.info(_msg("🖱️", "已通过 JS 兜底点击「发布」"))
                return True
        except Exception as e:
            kuaishou_logger.debug(_msg("😵", f"JS 点击发布失败: {e}"))

        return False

    async def _click_confirm_publish_if_any(self, page: Page) -> None:
        """若出现二次确认弹窗，点击「确认发布」。"""
        await page.wait_for_timeout(500)
        confirm_candidates = [
            page.get_by_role("button", name="确认发布"),
            page.get_by_text("确认发布", exact=True),
            page.locator('button:has-text("确认发布")').first,
        ]
        for btn in confirm_candidates:
            try:
                if await btn.count() and await btn.first.is_visible():
                    await btn.first.click(timeout=3000)
                    kuaishou_logger.info(_msg("🖱️", "已点击「确认发布」"))
                    return
            except Exception:
                continue


class KSVideo(KSBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str | None = None,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        thumbnail_path=None,
        desc: str | None = None,
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
        self.thumbnail_path = thumbnail_path
        self.desc = desc or ""
        self.dry_run = bool(dry_run)
        self.ai_generated = bool(ai_generated)

    async def validate_upload_args(self):
        await self.validate_base_args()
        # 视频标题允许为空
        self.title = "" if self.title is None else str(self.title)
        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def _locate_author_declaration_select(self, page: Page):
        """仅定位「作者声明」同一行内的下拉框，避免误点「作者服务」。"""
        labels = page.get_by_text("作者声明", exact=True)
        label_count = await labels.count()
        for idx in range(label_count):
            label = labels.nth(idx)
            try:
                if not await label.is_visible():
                    continue
            except Exception:
                continue

            scopes = [
                label.locator("xpath=following-sibling::*[1]"),
                label.locator("xpath=.."),
            ]
            for scope in scopes:
                try:
                    if not await scope.count():
                        continue
                    scope_text = (await scope.inner_text()).strip()
                    # 同一区块若主要是「作者服务」，跳过
                    if scope_text.startswith("作者服务") and not scope_text.startswith("作者声明"):
                        continue
                    select = scope.locator(
                        '.ant-select:not(.ant-select-dropdown), [role="combobox"], '
                        '[class*="select-selector"]'
                    ).first
                    if await select.count() and await select.is_visible():
                        return label, select
                    placeholder = scope.get_by_text("请选择作者声明").first
                    if await placeholder.count() and await placeholder.is_visible():
                        return label, placeholder
                except Exception:
                    continue

        return None, None

    async def set_ai_generated_declaration(self, page: Page) -> bool:
        """快手「作者声明」下拉选择「内容为AI生成」（无弹窗）。"""
        if not self.ai_generated:
            return False

        kuaishou_logger.info(_msg("🧍", "小人准备设置作者声明：内容为AI生成"))
        try:
            label, select = await self._locate_author_declaration_select(page)
            if not label or not select:
                kuaishou_logger.warning(_msg("😵", "没找到「作者声明」入口"))
                return False

            row = label.locator("xpath=..")
            try:
                row_text = (await row.inner_text()).strip()
                dropdown_open = page.locator(
                    '.ant-select-dropdown:visible, .ant-dropdown:visible, [role="listbox"]:visible'
                ).first
                if (
                    "内容为AI生成" in row_text
                    and not (await dropdown_open.count() and await dropdown_open.is_visible())
                ):
                    kuaishou_logger.info(_msg("🥳", "作者声明已是「内容为AI生成」，跳过"))
                    return True
            except Exception:
                pass

            await label.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)

            opened = False
            try:
                await select.click(timeout=3000)
                opened = True
                kuaishou_logger.info(_msg("🖱️", "已点击作者声明选择框"))
            except Exception:
                pass

            if not opened:
                kuaishou_logger.warning(_msg("😵", "无法打开作者声明下拉框"))
                return False

            await page.wait_for_timeout(500)

            option_candidates = [
                page.locator('.ant-select-dropdown:visible .ant-select-item-option').filter(
                    has_text="内容为AI生成"
                ).first,
                page.locator('.ant-select-dropdown:visible').get_by_text("内容为AI生成", exact=True).first,
                page.locator('[role="listbox"]:visible [role="option"]').filter(has_text="内容为AI生成").first,
            ]

            selected = False
            for opt in option_candidates:
                try:
                    if await opt.count() and await opt.is_visible():
                        await opt.click(timeout=3000)
                        selected = True
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(600)

            if selected:
                # 收起下拉，避免挡住底部「发布」
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)
                except Exception:
                    pass
                kuaishou_logger.success(_msg("🥳", "已选择作者声明：内容为AI生成"))
                return True

            kuaishou_logger.warning(_msg("😵", "打开了下拉，但没点到「内容为AI生成」"))
            return False
        except Exception as e:
            kuaishou_logger.warning(_msg("😵", f"设置作者声明失败: {e}"))
            return False

    async def handle_upload_error(self, page: Page):
        kuaishou_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def set_thumbnail(self, page: Page):
        if not self.thumbnail_path:
            return

        kuaishou_logger.info(_msg("🖼️", "小人准备设置封面"))

        cover_label = page.locator("span").filter(has_text="封面设置")
        await cover_label.wait_for(state="visible", timeout=30000)
        await cover_label.locator("xpath=../following-sibling::div[1]").locator('div').nth(0).click()

        modal = page.locator('div[role="document"].ant-modal')
        await modal.wait_for(state="visible", timeout=30000)

        upload_cover_tab = modal.get_by_text("上传封面", exact=True)
        await upload_cover_tab.wait_for(state="visible", timeout=10000)
        await upload_cover_tab.click()

        file_input = modal.locator('input[type="file"]')
        await file_input.wait_for(state="attached", timeout=30000)
        await file_input.set_input_files(self.thumbnail_path)
        await asyncio.sleep(1)

        confirm_button = modal.get_by_role("button", name="确认", exact=True)
        await confirm_button.wait_for(state="visible", timeout=10000)
        await confirm_button.click()

        await modal.wait_for(state="hidden", timeout=30000)
        kuaishou_logger.success(_msg("🥳", "封面已经设置完成"))

    async def upload(self, playwright: Playwright) -> None:
        kuaishou_logger.info(_msg("🧍", "小人先检查 cookie、视频文件、封面和发布时间"))
        await self.validate_upload_args()
        kuaishou_logger.info(_msg("🥳", "上传前检查通过"))

        if self.local_executable_path:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.local_executable_path,
            )
        else:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                channel="chrome",
            )
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto(KUAISHOU_UPLOAD_URL)
            kuaishou_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}.mp4"))
            kuaishou_logger.info(_msg("🧭", "小人正在赶往快手上传主页"))
            await page.wait_for_url(KUAISHOU_UPLOAD_URL_PATTERN)

            upload_button = page.locator("button[class^='_upload-btn']")
            await upload_button.wait_for(state="visible", timeout=10000)

            async with page.expect_file_chooser() as fc_info:
                await upload_button.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.file_path)

            await asyncio.sleep(2)

            know_button = page.locator('button[type="button"] span:text("我知道了")').first
            try:
                if await know_button.count() and await know_button.is_visible():
                    await know_button.click()
            except Exception:
                pass

            await self.close_guide_overlay(page)

            kuaishou_logger.info(_msg("✍️", "小人开始填描述和话题"))
            await page.get_by_text("描述").locator("xpath=following-sibling::div").click()
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            fill_text = (self.desc or self.title or "").strip()
            if fill_text:
                await page.keyboard.type(fill_text)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(400)

            await self.fill_tags(page)

            max_retries = 60
            retry_count = 0
            while retry_count < max_retries:
                try:
                    number = await page.locator("text=上传中").count()
                    if number == 0:
                        kuaishou_logger.success(_msg("🥳", "视频已经传完啦"))
                        break

                    if retry_count % 5 == 0:
                        kuaishou_logger.info(_msg("🏃", "小人正在努力上传视频"))

                    if await page.locator("text=上传失败").count():
                        await self.handle_upload_error(page)

                    await asyncio.sleep(2)
                except Exception as exc:
                    kuaishou_logger.warning(_msg("😵", f"检查上传状态时出错，小人继续重试: {exc}"))
                    await asyncio.sleep(2)
                retry_count += 1

            if retry_count == max_retries:
                kuaishou_logger.warning(_msg("😵", "超过最大重试次数，视频上传可能未完成"))

            await self.set_thumbnail(page)

            # 作者声明：内容为AI生成（下拉，无弹窗）
            await self.set_ai_generated_declaration(page)

            if self.publish_strategy == KUAISHOU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
                await self.set_schedule_time(page, self.publish_date)

            max_publish_retries = 600
            publish_retry_count = 0
            verification_waited = False

            if self.dry_run:
                kuaishou_logger.warning(_msg("🛑", "【仅预览不发布】已跳过点击发布按钮"))
                kuaishou_logger.info(_msg("👀", "请在浏览器窗口核对表单是否正确"))
                kuaishou_logger.info(_msg("⏳", "页面将保持打开约 120 秒后自动关闭"))
                try:
                    await page.screenshot(full_page=True, path=str(Path(self.account_file).with_name("dry_run_preview.png")))
                except Exception:
                    pass
                for i in range(120):
                    await asyncio.sleep(1)
                    if i > 0 and i % 30 == 0:
                        kuaishou_logger.info(_msg("⏳", f"预览中…还剩约 {120 - i} 秒自动关闭"))
                kuaishou_logger.info(_msg("🛑", "预览结束，关闭浏览器（未点击发布）"))
                upload_success = True
            else:
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
                                kuaishou_logger.warning(_msg("⚠️", "检测到验证弹窗！请在浏览器窗口中手动完成验证..."))
                                kuaishou_logger.info(_msg("⏳", "等待手动验证完成（最多180秒）..."))
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
                                        kuaishou_logger.success(_msg("✅", "验证已完成，继续发布流程"))
                                        verification_waited = True
                                        break
                                    if wait_i % 20 == 0 and wait_i > 0:
                                        kuaishou_logger.info(_msg("⏳", f"仍在等待验证完成...已等待{wait_i // 2}秒"))
                                else:
                                    verification_waited = True

                        clicked = await self._click_publish_button(page)
                        if not clicked and publish_retry_count % 20 == 0:
                            kuaishou_logger.warning(
                                _msg("⚠️", f"未找到可点击的「发布」按钮（第{publish_retry_count}次）")
                            )

                        await self._click_confirm_publish_if_any(page)

                        await page.wait_for_url(KUAISHOU_MANAGE_URL_PATTERN, timeout=5000)
                        kuaishou_logger.success(_msg("🥳", "视频发布成功，小人开心收工"))
                        break
                    except Exception as exc:
                        if publish_retry_count % 10 == 0:
                            kuaishou_logger.info(_msg("🏃", f"小人正在冲刺发布视频（第{publish_retry_count}次）"))
                        if self.debug and publish_retry_count <= 5:
                            await page.screenshot(full_page=True)
                        await asyncio.sleep(1)
                else:
                    kuaishou_logger.error(_msg("❌", f"发布超时：{max_publish_retries}次尝试后仍未成功"))
                    raise RuntimeError(f"发布超时：{max_publish_retries}次尝试后仍未成功")

                upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                kuaishou_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)


class KSNote(KSBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str | None = None,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
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
        self.title = title or (self.note[:20] if self.note else "")
        self.tags = tags or []

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("快手图文上传时，title 是必须的")
        if not self.image_paths:
            raise ValueError("快手图文上传时，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        kuaishou_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))
        kuaishou_logger.info(_msg("🔀", "小人正在切换到图文发布"))
        await page.locator('div[role="tablist"] div[role="tab"]:has-text("图文")').click()
        await page.wait_for_timeout(1000)

        kuaishou_logger.info(_msg("📤", "小人正在上传图片"))
        upload_button = page.locator("button[class^='_upload-btn']").filter(has_text="上传图片")
        await upload_button.wait_for(state="visible", timeout=10000)

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.image_paths)

        know_button = page.locator('button[type="button"] span:text("我知道了")').first
        try:
            if await know_button.count() and await know_button.is_visible():
                await know_button.click()
        except Exception:
            pass

        await self.close_guide_overlay(page)

        kuaishou_logger.info(_msg("✍️", "小人开始填写图文内容和话题"))
        await page.get_by_text("描述").locator("xpath=following-sibling::div").click()
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        note_text = (self.note or "").strip()
        if note_text:
            await page.keyboard.type(note_text)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(400)

        await self.fill_tags(page)

        max_retries = 60
        retry_count = 0
        while retry_count < max_retries:
            try:
                number = await page.locator("text=上传中").count()
                if number == 0:
                    kuaishou_logger.success(_msg("🥳", "图文素材已经传完啦"))
                    break

                if retry_count % 5 == 0:
                    kuaishou_logger.info(_msg("🏃", "小人正在努力上传图文素材"))

                if await page.locator("text=上传失败").count():
                    kuaishou_logger.warning(_msg("😵", "图文素材上传摔了一跤，小人马上重新上传"))
                    await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.image_paths)

                await asyncio.sleep(2)
            except Exception as exc:
                kuaishou_logger.warning(_msg("😵", f"检查图文上传状态时出错，小人继续重试: {exc}"))
                await asyncio.sleep(2)
            retry_count += 1

        if retry_count == max_retries:
            kuaishou_logger.warning(_msg("😵", "超过最大重试次数，图文上传可能未完成"))

        if self.publish_strategy == KUAISHOU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time(page, self.publish_date)

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
                        kuaishou_logger.warning(_msg("⚠️", "检测到验证弹窗！请在浏览器窗口中手动完成验证..."))
                        kuaishou_logger.info(_msg("⏳", "等待手动验证完成（最多180秒）..."))
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
                                kuaishou_logger.success(_msg("✅", "验证已完成，继续发布流程"))
                                verification_waited = True
                                break
                            if wait_i % 20 == 0 and wait_i > 0:
                                kuaishou_logger.info(_msg("⏳", f"仍在等待验证完成...已等待{wait_i // 2}秒"))
                        else:
                            verification_waited = True

                clicked = await self._click_publish_button(page)
                if not clicked and publish_retry_count % 20 == 0:
                    kuaishou_logger.warning(
                        _msg("⚠️", f"未找到可点击的「发布」按钮（第{publish_retry_count}次）")
                    )

                await self._click_confirm_publish_if_any(page)

                await page.wait_for_url(KUAISHOU_MANAGE_URL_PATTERN, timeout=5000)
                kuaishou_logger.success(_msg("🥳", "图文发布成功，小人开心收工"))
                break
            except Exception as exc:
                if publish_retry_count % 10 == 0:
                    kuaishou_logger.info(_msg("🏃", f"小人正在冲刺发布图文（第{publish_retry_count}次）"))
                if self.debug and publish_retry_count <= 5:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(1)
        else:
            kuaishou_logger.error(_msg("❌", f"发布超时：{max_publish_retries}次尝试后仍未成功"))

    async def upload(self, playwright: Playwright) -> None:
        kuaishou_logger.info(_msg("🧍", "小人先检查 cookie、图片和发布时间"))
        await self.validate_upload_args()
        kuaishou_logger.info(_msg("🥳", "图文上传前检查通过"))

        if self.local_executable_path:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.local_executable_path,
            )
        else:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                channel="chrome",
            )
        context = await browser.new_context(storage_state=self.account_file)
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto(KUAISHOU_UPLOAD_URL)
            kuaishou_logger.info(_msg("🧭", "小人正在赶往快手图文发布页"))
            await page.wait_for_url(KUAISHOU_UPLOAD_URL_PATTERN)

            await self.upload_note_content(page)
            upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                kuaishou_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
