# -*- coding: utf-8 -*-
from datetime import datetime

import asyncio
import inspect
import os
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from utils.base_social_media import set_init_script
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import douyin_logger

DOUYIN_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
DOUYIN_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(success: bool, status: str, message: str, account_file: str, qrcode: dict | None = None, current_url: str = "") -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context(storage_state=account_file)
            context = await set_init_script(context)
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            try:
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
            except Exception:
                return False

            if await page.get_by_text("手机号登录").count() or await page.get_by_text("扫码登录").count():
                return False

            return True
        finally:
            await browser.close()


async def douyin_setup(account_file, handle=False, return_detail=False, qrcode_callback=None, headless: bool = LOCAL_CHROME_HEADLESS):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        douyin_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await douyin_cookie_gen(account_file, qrcode_callback=qrcode_callback, headless=headless)
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def _extract_douyin_qrcode_src(page: Page) -> str:
    scan_login_tab = page.get_by_text("扫码登录", exact=True).first
    await scan_login_tab.wait_for(timeout=30000)

    qrcode_img = (
        scan_login_tab
        .locator("..")
        .locator("xpath=following-sibling::div[1]")
        .locator('img[aria-label="二维码"]')
        .first
    )

    if not await qrcode_img.count():
        qrcode_img = page.get_by_role("img", name="二维码").first

    await qrcode_img.wait_for(state="visible", timeout=30000)
    src = await qrcode_img.get_attribute("src")
    if not src:
        raise RuntimeError("未获取到抖音登录二维码地址")

    return src


async def _save_douyin_qrcode(page: Page, account_file: str, previous_qrcode_path: Path | None = None, qrcode_callback=None) -> dict:
    qrcode_src = await _extract_douyin_qrcode_src(page)
    qrcode_path = save_data_url_image(qrcode_src, build_login_qrcode_path(account_file))
    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))
    douyin_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "抖音APP")
    else:
        douyin_logger.warning(_msg("😵", f"终端没法完整显示二维码，请打开 {qrcode_path} 扫码"))
    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_douyin_login_completed(page: Page) -> bool:
    if not page.url.startswith("https://creator.douyin.com/creator-micro/home"):
        return False

    login_markers = [
        page.get_by_text("扫码登录", exact=True).first,
        page.get_by_text("手机号登录", exact=True).first,
        page.get_by_text("二维码失效", exact=True).first,
        page.get_by_role("img", name="二维码").first,
    ]

    for marker in login_markers:
        if not await marker.count():
            continue
        try:
            if await marker.is_visible():
                return False
        except Exception:
            continue

    return True


async def _wait_for_douyin_login(page: Page, account_file: str, qrcode_info: dict, qrcode_callback=None, poll_interval: int = 3, max_checks: int = 100) -> dict:
    qrcode_path = Path(qrcode_info["image_path"])
    for _ in range(max_checks):
        if await _is_douyin_login_completed(page):
            douyin_logger.info(_msg("🥳", f"扫码成功，已经跳转到登录后页面: {page.url}"))
            return _build_login_result(True, "success", "抖音扫码登录成功", account_file, qrcode_info, page.url)

        expired_box = page.get_by_text("二维码失效", exact=True).locator("..").first
        if await expired_box.count() and await expired_box.is_visible():
            douyin_logger.warning(_msg("😵", "二维码失效了，小人马上去刷新"))
            await expired_box.click()
            await asyncio.sleep(1)
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_path, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])

        await asyncio.sleep(poll_interval)

    return _build_login_result(False, "timeout", "等待抖音扫码登录超时", account_file, qrcode_info, page.url)


async def douyin_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context()
        context = await set_init_script(context)
        qrcode_path = None
        result = _build_login_result(False, "failed", "抖音登录失败", account_file)
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/")
            qrcode_info = await _save_douyin_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            douyin_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_douyin_login(
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
                        "抖音扫码流程结束，但 cookie 校验失败",
                        account_file,
                        qrcode_info,
                        page.url,
                    )
        except Exception as exc:
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=page.url if "page" in locals() else "")
        finally:
            if remove_qrcode_file(qrcode_path):
                douyin_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if not result["success"]:
                douyin_logger.error(_msg("😢", f"登录失败: {result['message']}"))
            await context.close()
            await browser.close()
        return result


class DouYinBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = account_file
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成抖音登录: {self.account_file}")
        if not await cookie_auth(self.account_file):
            raise RuntimeError(f"cookie文件已失效，请先完成抖音登录: {self.account_file}")
        # 传入了具体 datetime 却忘了 strategy 时，自动切到定时（与快手一致）
        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_IMMEDIATE and isinstance(
            self.publish_date, datetime
        ):
            douyin_logger.warning(_msg("⚠️", "检测到定时时间但策略为立即发布，已自动切换为定时发布"))
            self.publish_strategy = DOUYIN_PUBLISH_STRATEGY_SCHEDULED

        if self.publish_strategy not in {DOUYIN_PUBLISH_STRATEGY_IMMEDIATE, DOUYIN_PUBLISH_STRATEGY_SCHEDULED}:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

        douyin_logger.info(
            _msg(
                "🧭",
                f"发布策略={self.publish_strategy}, 发布时间="
                f"{self.publish_date if self.publish_date != 0 else '立即'}",
            )
        )

    async def _is_douyin_schedule_selected(self, page) -> bool:
        label = page.locator("[class^='radio']:has-text('定时发布')").first
        if not await label.count():
            label = page.locator("label").filter(has_text="定时发布").first
        if not await label.count():
            return False
        checked = await label.get_attribute("data-checked")
        if checked == "true":
            return True
        return bool(await label.locator("input:checked").count())

    async def set_schedule_time_douyin(self, page, publish_date):
        douyin_logger.info(
            _msg("🕒", f"小人准备设置定时发布: {publish_date.strftime('%Y-%m-%d %H:%M')}")
        )

        schedule_title = page.get_by_text("发布时间", exact=True).first
        if await schedule_title.count():
            await schedule_title.scroll_into_view_if_needed()

        # DOM: label.radio-* + data-checked；兼容文案/开关形态
        schedule_label = page.locator("[class^='radio']:has-text('定时发布')").first
        if not await schedule_label.count():
            schedule_label = page.locator("label").filter(has_text="定时发布").first
        if not await schedule_label.count():
            schedule_label = page.get_by_text("定时发布", exact=True).last

        if not await schedule_label.count():
            raise RuntimeError("页面上找不到抖音「定时发布」选项")

        await schedule_label.scroll_into_view_if_needed()
        if not await self._is_douyin_schedule_selected(page):
            native = schedule_label.locator("input.radio-native-p6VBGt, input[type='checkbox'], input[type='radio']").first
            clicked = False
            if await native.count():
                try:
                    await native.click(force=True, timeout=3000)
                    clicked = True
                except Exception as e:
                    douyin_logger.debug(_msg("🧍", f"定时 radio input 点击失败: {e}"))
            if not clicked:
                try:
                    await schedule_label.click(force=True, timeout=4000)
                    clicked = True
                except Exception:
                    await schedule_label.evaluate("el => el.click()")
                    clicked = True
            await asyncio.sleep(0.8)

        if not await self._is_douyin_schedule_selected(page):
            # 最后兜底：按文案 JS 点击
            ok = await page.evaluate(
                """() => {
                    const labels = [...document.querySelectorAll('label')];
                    const label = labels.find(el => (el.innerText || '').trim().startsWith('定时发布'));
                    if (!label) return false;
                    const input = label.querySelector('input');
                    if (input) input.click();
                    else label.click();
                    return true;
                }"""
            )
            await asyncio.sleep(0.8)
            if not ok or not await self._is_douyin_schedule_selected(page):
                raise RuntimeError("未能切换到抖音「定时发布」（data-checked 仍为 false）")

        douyin_logger.info(_msg("🖱️", "已选中「定时发布」"))
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")

        date_input = page.locator('.semi-input[placeholder="日期和时间"]').first
        if not await date_input.count():
            date_input = page.locator('input[placeholder*="日期"]').first
        await date_input.wait_for(state="visible", timeout=8000)
        await date_input.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)
        douyin_logger.success(
            _msg("🥳", f"定时发布时间已设置: {publish_date_hour}")
        )

    async def fill_title_and_description(self, page: Page, title: str, description: str, tags: list[str] | None = None):
        description_section = (
            page.get_by_text("作品描述", exact=True)
            .locator("xpath=ancestor::div[2]")
            .locator("xpath=following-sibling::div[1]")
        )

        title_input = description_section.locator('input[type="text"]').first
        await title_input.wait_for(state="visible", timeout=10000)
        # 标题允许为空，空字符串时清空输入框即可
        await title_input.fill((title or "")[:30])

        description_editor = description_section.locator('.zone-container[contenteditable="true"]').first
        await description_editor.wait_for(state="visible", timeout=10000)
        await description_editor.click()
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        if description:
            await page.keyboard.type(description)

        for tag in tags or []:
            await page.keyboard.type(" #" + tag)
            await page.keyboard.press("Space")

    async def set_location(self, page: Page, location: str = ""):
        if not location:
            return
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def handle_product_dialog(self, page: Page, product_title: str):
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            douyin_logger.error(_msg("😵", "没找到商品短标题输入框"))
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“完成编辑”按钮"))
            await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
            return True

        douyin_logger.error(_msg("😵", "“完成编辑”按钮是灰的，小人先把弹窗关掉"))
        cancel_button = page.locator('button:has-text("取消")')
        if await cancel_button.count():
            await cancel_button.click()
        else:
            close_button = page.locator(".semi-modal-close")
            await close_button.click()
        await page.wait_for_selector(".semi-modal-content", state="hidden", timeout=5000)
        return False

    async def set_product_link(self, page: Page, product_link: str, product_title: str):
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = page.get_by_text("添加标签").locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                douyin_logger.error(_msg("😵", "没找到标签下拉框"))
                return False
            douyin_logger.debug(_msg("🧍", "找到标签下拉框，小人准备选择“购物车”"))
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            douyin_logger.debug(_msg("🥳", "已经选中“购物车”"))

            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            douyin_logger.debug(_msg("🔗", f"商品链接已经填好了: {product_link}"))

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                douyin_logger.error(_msg("😵", "“添加链接”按钮现在点不了"))
                return False
            await add_button.click()
            douyin_logger.debug(_msg("🥳", "已点击“添加链接”按钮"))

            await page.wait_for_timeout(2000)
            error_modal = page.locator("text=未搜索到对应商品")
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                douyin_logger.error(_msg("😢", "这个商品链接无效"))
                return False

            if not await self.handle_product_dialog(page, product_title):
                return False

            douyin_logger.debug(_msg("🥳", "商品链接设置好了"))
            return True
        except Exception as e:
            douyin_logger.error(_msg("😢", f"设置商品链接时出错: {str(e)}"))
            return False


class DouYinVideo(DouYinBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_landscape_path=None,
        productLink="",
        productTitle="",
        thumbnail_portrait_path=None,
        desc: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
        ai_generated: bool = False,
        dry_run: bool = False,
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
        self.tags = tags
        self.thumbnail_landscape_path = thumbnail_landscape_path
        self.thumbnail_portrait_path = thumbnail_portrait_path
        self.productLink = productLink
        self.productTitle = productTitle
        self.desc = desc or ""
        self.ai_generated = bool(ai_generated)
        self.dry_run = bool(dry_run)

    async def validate_upload_args(self):
        await self.validate_base_args()
        # 视频标题允许为空：抖音创作者中心可不填标题
        self.title = "" if self.title is None else str(self.title)

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_landscape_path:
            self.thumbnail_landscape_path = str(self.validate_image_file(self.thumbnail_landscape_path))
        if self.thumbnail_portrait_path:
            self.thumbnail_portrait_path = str(self.validate_image_file(self.thumbnail_portrait_path))

    async def set_ai_generated_declaration(self, page: Page) -> bool:
        """打开「自主声明」→ 单选「内容由AI生成」→ 确定。

        抖音实际弹窗标题是「对作品内容添加声明」（不是「添加自主声明」）。
        """
        if not self.ai_generated:
            return False

        douyin_logger.info(_msg("🧍", "小人准备勾选自主声明：内容由AI生成"))
        try:
            # 入口已显示具体声明且弹窗未开 → 跳过
            try:
                if not await self._is_ai_declaration_dialog_open(page):
                    please = page.get_by_text("请选择自主声明", exact=True).first
                    if not await please.count():
                        row = page.locator('div:has-text("自主声明")').filter(has_text="内容由AI生成").first
                        if await row.count() and await row.is_visible():
                            douyin_logger.info(_msg("🥳", "自主声明已是「内容由AI生成」，跳过"))
                            return True
            except Exception:
                pass

            # 1) 打开入口
            if not await self._is_ai_declaration_dialog_open(page):
                entry_candidates = [
                    page.get_by_text("请选择自主声明", exact=True).first,
                    page.locator('div:has-text("自主声明"):has-text("请选择自主声明")').first,
                    page.locator("text=请选择自主声明").first,
                ]
                opened = False
                for entry in entry_candidates:
                    try:
                        if await entry.count() and await entry.is_visible():
                            await entry.scroll_into_view_if_needed()
                            await entry.click(timeout=5000)
                            opened = True
                            douyin_logger.info(_msg("🖱️", "已点击自主声明入口"))
                            break
                    except Exception:
                        continue
                if not opened:
                    douyin_logger.warning(_msg("😵", "没找到「请选择自主声明」入口"))
                    return False

            # 2) 等弹窗（真实标题：对作品内容添加声明）
            if not await self._wait_ai_declaration_dialog(page, timeout_ms=12000):
                douyin_logger.warning(_msg("😵", "点击入口后未出现声明弹窗（期望：对作品内容添加声明）"))
                return False
            douyin_logger.info(_msg("🥳", "声明弹窗已打开"))
            await page.wait_for_timeout(400)

            # 3) 选中 radio
            if not await self._select_ai_generated_radio(page):
                douyin_logger.warning(_msg("😵", "未能选中「内容由AI生成」"))
                return False
            await page.wait_for_timeout(500)

            # 4) 确定
            if await self._click_ai_declaration_confirm(page):
                douyin_logger.success(_msg("🥳", "已勾选自主声明：内容由AI生成，并点击了确定"))
                return True

            douyin_logger.warning(_msg("😵", "选中了 AI 选项，但没点到「确定」"))
            return False
        except Exception as e:
            douyin_logger.warning(_msg("😵", f"设置自主声明失败: {e}"))
            return False

    async def _is_ai_declaration_dialog_open(self, page: Page) -> bool:
        markers = [
            page.get_by_text("对作品内容添加声明", exact=True).first,
            page.get_by_text("请选择声明类型", exact=False).first,
            page.get_by_text("添加自主声明", exact=True).first,
        ]
        for m in markers:
            try:
                if await m.count() and await m.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _wait_ai_declaration_dialog(self, page: Page, timeout_ms: int = 10000) -> bool:
        elapsed = 0.0
        deadline = timeout_ms / 1000
        while elapsed < deadline:
            if await self._is_ai_declaration_dialog_open(page):
                return True
            try:
                radio = page.get_by_text("内容由AI生成", exact=True).first
                cancel = page.get_by_role("button", name="取消").first
                if (
                    await radio.count()
                    and await radio.is_visible()
                    and await cancel.count()
                    and await cancel.is_visible()
                ):
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(250)
            elapsed += 0.25
        return False

    async def _select_ai_generated_radio(self, page: Page) -> bool:
        """选中弹窗内「内容由AI生成」单选项。"""
        radio_label = page.locator("label.semi-radio").filter(has_text="内容由AI生成").first
        if not await radio_label.count():
            radio_label = page.locator(".semi-radio").filter(has_text="内容由AI生成").first
        if not await radio_label.count():
            radio_label = page.get_by_text("内容由AI生成", exact=True).locator(
                "xpath=ancestor::label[1]"
            ).first

        try:
            await radio_label.wait_for(state="visible", timeout=8000)
        except Exception:
            douyin_logger.warning(_msg("😵", "弹窗里找不到「内容由AI生成」选项"))
            return False

        cls = (await radio_label.get_attribute("class")) or ""
        if "semi-radio-checked" in cls:
            douyin_logger.info(_msg("🥳", "「内容由AI生成」已是选中状态"))
            return True

        radio_input = radio_label.locator('input[type="radio"]').first
        if not await radio_input.count():
            radio_input = page.locator(
                'label.semi-radio:has-text("内容由AI生成") input[type="radio"]'
            ).first

        clicked = False
        if await radio_input.count():
            try:
                await radio_input.check(force=True, timeout=3000)
                clicked = True
            except Exception as e:
                douyin_logger.debug(_msg("🧍", f"radio.check 失败: {e}"))

        if not clicked:
            target = page.locator("label.semi-radio").filter(has_text="内容由AI生成").first
            if not await target.count():
                target = radio_label
            try:
                await target.click(force=True, timeout=3000)
                clicked = True
            except Exception:
                try:
                    await target.evaluate("el => el.click()")
                    clicked = True
                except Exception as e:
                    douyin_logger.debug(_msg("🧍", f"label 点击失败: {e}"))

        if not clicked:
            clicked = await page.evaluate(
                """() => {
                    const markers = ['对作品内容添加声明', '请选择声明类型', '添加自主声明'];
                    const roots = Array.from(document.querySelectorAll('.semi-modal, [role="dialog"], .semi-modal-wrap, body'));
                    const root = roots.find(r => markers.some(t => (r.innerText || '').includes(t)) && r.offsetParent !== null) || document.body;
                    const labels = Array.from(root.querySelectorAll('label.semi-radio, label, .semi-radio'));
                    const label = labels.find(el => (el.innerText || '').includes('内容由AI生成'));
                    if (!label) return false;
                    const input = label.querySelector('input[type=radio]');
                    if (input) { input.click(); return true; }
                    label.click();
                    return true;
                }"""
            )

        await page.wait_for_timeout(400)
        label = page.locator("label.semi-radio").filter(has_text="内容由AI生成").first
        if await label.count():
            cls2 = (await label.get_attribute("class")) or ""
            if "semi-radio-checked" in cls2 or await label.locator("input:checked").count():
                douyin_logger.info(_msg("🖱️", "已选择「内容由AI生成」"))
                return True

        if clicked:
            douyin_logger.info(_msg("🖱️", "已点击「内容由AI生成」（未读到 checked class，仍继续）"))
            return True
        return False

    async def _click_ai_declaration_confirm(self, page: Page) -> bool:
        """在声明弹窗内点击确定。"""
        dialog_markers = ("对作品内容添加声明", "请选择声明类型", "添加自主声明")
        dialog_selectors = [
            'div[role="dialog"]:has-text("对作品内容添加声明")',
            '.semi-modal:has-text("对作品内容添加声明")',
            '.semi-modal-content:has-text("对作品内容添加声明")',
            '.semi-modal-wrap:has-text("对作品内容添加声明")',
            'div[role="dialog"]:has-text("请选择声明类型")',
            '.semi-modal:has-text("请选择声明类型")',
            'div[role="dialog"]:has-text("添加自主声明")',
            '.semi-modal:has-text("添加自主声明")',
        ]

        dialog = None
        for sel in dialog_selectors:
            loc = page.locator(sel).first
            try:
                if await loc.count() and await loc.is_visible():
                    dialog = loc
                    break
            except Exception:
                continue

        confirm_candidates = []
        if dialog is not None:
            confirm_candidates.extend(
                [
                    dialog.locator('.semi-modal-footer button:has-text("确定")').first,
                    dialog.locator(".semi-modal-footer .semi-button-primary").first,
                    dialog.locator('button.semi-button-primary:has-text("确定")').first,
                    dialog.get_by_role("button", name="确定").first,
                    dialog.locator('button:has-text("确定")').last,
                ]
            )
        confirm_candidates.extend(
            [
                page.locator('.semi-modal-footer button:has-text("确定"):visible').first,
                page.locator(".semi-modal-footer .semi-button-primary:visible").first,
                page.locator('div[role="dialog"] button:has-text("确定"):visible').first,
                page.locator(".semi-modal-wrap button.semi-button-primary:visible").last,
                page.locator('button:has-text("确定"):visible').last,
            ]
        )

        for confirm in confirm_candidates:
            try:
                if not await confirm.count() or not await confirm.is_visible():
                    continue
                for _ in range(16):
                    disabled = await confirm.get_attribute("disabled")
                    aria_disabled = await confirm.get_attribute("aria-disabled")
                    cls = (await confirm.get_attribute("class")) or ""
                    if (
                        disabled is None
                        and aria_disabled not in ("true", "True")
                        and "disabled" not in cls
                        and "semi-button-disabled" not in cls
                    ):
                        break
                    await page.wait_for_timeout(250)
                else:
                    douyin_logger.debug(_msg("🧍", "确定按钮仍禁用，换候选"))
                    continue

                await confirm.scroll_into_view_if_needed()
                try:
                    await confirm.click(timeout=3000)
                except Exception:
                    try:
                        await confirm.click(force=True, timeout=3000)
                    except Exception:
                        await confirm.evaluate("el => el.click()")

                await page.wait_for_timeout(1000)
                if not await self._is_ai_declaration_dialog_open(page):
                    return True
                douyin_logger.debug(_msg("🧍", "点了确定但弹窗还在，继续尝试"))
            except Exception as e:
                douyin_logger.debug(_msg("🧍", f"点击确定候选失败: {e}"))
                continue

        try:
            cancel = page.get_by_role("button", name="取消").last
            if await cancel.count() and await cancel.is_visible():
                sibling = cancel.locator("xpath=following-sibling::button[1]").first
                if not await sibling.count():
                    sibling = cancel.locator("xpath=../button[contains(., '确定')]").first
                if await sibling.count():
                    await sibling.click(force=True)
                    await page.wait_for_timeout(800)
                    if not await self._is_ai_declaration_dialog_open(page):
                        return True
        except Exception:
            pass

        try:
            clicked = await page.evaluate(
                """(markers) => {
                    const roots = Array.from(document.querySelectorAll('.semi-modal, [role="dialog"], .semi-modal-wrap'));
                    const modal = roots.find(m => markers.some(t => (m.innerText || '').includes(t)) && m.offsetParent !== null);
                    if (!modal) return false;
                    const buttons = Array.from(modal.querySelectorAll('button'));
                    const ok = buttons.find(b => (b.innerText || '').trim() === '确定' && !b.disabled
                        && !(b.className || '').includes('disabled'))
                        || buttons.find(b => (b.className || '').includes('semi-button-primary') && !b.disabled);
                    if (!ok) return false;
                    ok.click();
                    return true;
                }""",
                list(dialog_markers),
            )
            if clicked:
                await page.wait_for_timeout(1000)
                if not await self._is_ai_declaration_dialog_open(page):
                    return True
        except Exception:
            pass

        return False

    async def handle_upload_error(self, page):
        douyin_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def handle_auto_video_cover(self, page):
        if await page.get_by_text("请设置封面后再发布").first.is_visible():
            douyin_logger.info(_msg("🧍", "发布前还得先把封面弄好"))
            recommend_cover = page.locator('[class^="recommendCover-"]').first
            if await recommend_cover.count():
                douyin_logger.info(_msg("🏃", "小人去选第一个推荐封面"))
                try:
                    await recommend_cover.click()
                    await asyncio.sleep(1)
                    confirm_text = "是否确认应用此封面？"
                    if await page.get_by_text(confirm_text).first.is_visible():
                        douyin_logger.info(_msg("🪟", f"弹出确认框了: {confirm_text}"))
                        await page.get_by_role("button", name="确定").click()
                        douyin_logger.info(_msg("🥳", "推荐封面已经应用"))
                        await asyncio.sleep(1)
                    douyin_logger.info(_msg("🥳", "封面选择流程完成"))
                    return True
                except Exception as e:
                    douyin_logger.warning(_msg("😵", f"推荐封面没选成功: {e}"))
        return False

    async def set_thumbnail(self, page: Page):
        if not self.thumbnail_landscape_path and not self.thumbnail_portrait_path:
            return

        douyin_logger.info(_msg("🏃", "小人正在设置视频封面"))
        await page.click('text="选择封面"')
        cover_locator_str = 'div[id*="creator-content-modal"]'
        cover_locator = page.locator(cover_locator_str)
        await page.wait_for_selector(cover_locator_str)

        upload_input = cover_locator.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input")

        if self.thumbnail_landscape_path:
            await page.wait_for_timeout(1000)
            await upload_input.set_input_files(self.thumbnail_landscape_path)
            await page.wait_for_timeout(2000)
            douyin_logger.info(_msg("🖼️", "横版封面上传完成"))

        if self.thumbnail_portrait_path:
            await cover_locator.locator("div[class*='steps'] div").nth(1).click()
            await page.wait_for_timeout(1000)
            await upload_input.set_input_files(self.thumbnail_portrait_path)
            await page.wait_for_timeout(2000)
            douyin_logger.info(_msg("🖼️", "竖版封面上传完成"))

        await cover_locator.locator('button:visible:has-text("完成")').click()
        douyin_logger.info(_msg("🥳", "视频封面设置完成"))
        await page.wait_for_selector("div.extractFooter", state="detached")

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、视频文件、封面和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "上传前检查通过"))

        browser = await playwright.chromium.launch(headless=self.headless, channel="chrome")
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        page = await context.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        douyin_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}.mp4"))
        douyin_logger.info(_msg("🧭", "小人正在赶往上传主页"))
        await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        await page.locator("div[class^='container'] input").set_input_files(self.file_path)

        while True:
            try:
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/publish?enter_from=publish_page",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入 version_1 发布页面"))
                break
            except Exception:
                try:
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
                        timeout=3000,
                    )
                    douyin_logger.info(_msg("🥳", "已经进入 version_2 发布页面"))
                    break
                except Exception:
                    douyin_logger.debug(_msg("🧍", "还没进到视频发布页面，小人继续等一会"))
                    await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.desc or self.title, self.tags)
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        while True:
            try:
                number = await page.locator('[class^="long-card"] div:has-text("重新上传")').count()
                if number > 0:
                    douyin_logger.success(_msg("🥳", "视频已经传完啦"))
                    break
                douyin_logger.info(_msg("🏃", "小人正在努力上传视频"))
                await asyncio.sleep(2)
                if await page.locator('div.progress-div > div:has-text("上传失败")').count():
                    douyin_logger.error(_msg("😵", "检测到上传失败，小人准备重试"))
                    await self.handle_upload_error(page)
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等视频上传完成"))
                await asyncio.sleep(2)

        if self.productLink and self.productTitle:
            douyin_logger.info(_msg("🛒", "小人正在设置商品链接"))
            await self.set_product_link(page, self.productLink, self.productTitle)
            douyin_logger.info(_msg("🥳", "商品链接设置完成"))

        await self.set_thumbnail(page)

        # 自主声明：内容由AI生成
        await self.set_ai_generated_declaration(page)

        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        if await page.locator(third_part_element).count():
            if "semi-switch-checked" not in await page.eval_on_selector(third_part_element, "div => div.className"):
                await page.locator(third_part_element).locator("input.semi-switch-native-control").click()

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        # 发布前先截图，方便调试
        if self.debug:
            await page.screenshot(full_page=True)
            douyin_logger.info(_msg("📸", "发布前截图已保存"))

        # 调试模式：只填表、不点「发布」，浏览器停住方便核对
        if self.dry_run:
            douyin_logger.warning(_msg("🛑", "【仅预览不发布】已跳过点击发布按钮"))
            douyin_logger.info(_msg("👀", "请在浏览器窗口核对：标题/话题/自主声明等是否正确"))
            douyin_logger.info(_msg("⏳", "页面将保持打开约 120 秒后自动关闭（也可手动关浏览器）"))
            try:
                await page.screenshot(full_page=True, path=str(Path(self.account_file).with_name("dry_run_preview.png")))
                douyin_logger.info(_msg("📸", "预览截图已保存到 cookiesFile/dry_run_preview.png 附近"))
            except Exception as e:
                douyin_logger.debug(_msg("🧍", f"预览截图失败: {e}"))
            # 保持页面打开，方便用户肉眼核对
            for i in range(120):
                await asyncio.sleep(1)
                if i > 0 and i % 30 == 0:
                    douyin_logger.info(_msg("⏳", f"预览中…还剩约 {120 - i} 秒自动关闭"))
            douyin_logger.info(_msg("🛑", "预览结束，关闭浏览器（未点击发布）"))
            await context.storage_state(path=self.account_file)
            await context.close()
            await browser.close()
            return

        max_retries = 600  # 最多重试 600 次（约 300 秒，预留手动验证码时间）
        retry_count = 0
        verification_waited = False
        while retry_count < max_retries:
            retry_count += 1
            try:
                # 检测是否有验证码/安全验证弹窗，如果有则等待用户手动处理
                verification_indicators = [
                    'text="获取验证码"',
                    'text="请输入验证码"',
                    'text="安全验证"',
                    'text="请完成验证"',
                    'text="滑块验证"',
                    '.captcha-verify-container',
                    '[class*="captcha"]',
                    '[class*="verify"]',
                ]
                has_verification = False
                for selector in verification_indicators:
                    try:
                        if await page.locator(selector).count() > 0:
                            has_verification = True
                            break
                    except Exception:
                        continue

                if has_verification and not verification_waited:
                    douyin_logger.warning(_msg("⚠️", "检测到验证码弹窗！请在浏览器窗口中手动完成验证..."))
                    douyin_logger.info(_msg("⏳", "等待手动验证完成（最多180秒）..."))
                    # 等待验证码弹窗消失（用户手动完成验证）
                    try:
                        for wait_i in range(360):  # 最多等180秒（3分钟）
                            await asyncio.sleep(0.5)
                            still_has_verification = False
                            for selector in verification_indicators:
                                try:
                                    if await page.locator(selector).count() > 0:
                                        still_has_verification = True
                                        break
                                except Exception:
                                    continue
                            if not still_has_verification:
                                douyin_logger.success(_msg("✅", "验证已完成，继续发布流程"))
                                verification_waited = True
                                break
                            if wait_i % 20 == 0 and wait_i > 0:
                                douyin_logger.info(_msg("⏳", f"仍在等待验证完成...已等待{wait_i // 2}秒"))
                        else:
                            douyin_logger.warning(_msg("⚠️", "等待验证超时，继续尝试发布"))
                            verification_waited = True
                    except Exception:
                        verification_waited = True

                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                    douyin_logger.info(_msg("🖱️", f"已点击发布按钮（第{retry_count}次尝试）"))
                else:
                    # 尝试其他可能的发布按钮选择器
                    alt_button = page.locator('button:has-text("发布")').first
                    if await alt_button.count():
                        await alt_button.click()
                        douyin_logger.info(_msg("🖱️", f"已点击备选发布按钮（第{retry_count}次尝试）"))
                    else:
                        if retry_count % 20 == 0:
                            douyin_logger.warning(_msg("⚠️", f"未找到发布按钮（第{retry_count}次尝试），页面标题: {await page.title()}"))
                        if self.debug and retry_count <= 3:
                            await page.screenshot(full_page=True)
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/content/manage**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "视频发布成功，小人开心收工"))
                break
            except Exception as e:
                await self.handle_auto_video_cover(page)
                if retry_count % 10 == 0:
                    douyin_logger.info(_msg("🏃", f"小人正在冲刺发布视频（第{retry_count}次）"))
                if self.debug and retry_count <= 5:
                    await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)
        else:
            douyin_logger.error(_msg("❌", f"发布超时：{max_retries}次尝试后仍未成功，请检查抖音页面是否有弹窗或变更"))
            if self.debug:
                await page.screenshot(full_page=True)
            raise RuntimeError(f"发布超时：{max_retries}次尝试后仍未成功")

        await context.storage_state(path=self.account_file)
        douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
        await asyncio.sleep(2)
        await context.close()
        await browser.close()

    async def douyin_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.douyin_upload_video()


class DouYinNote(DouYinBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        publish_strategy: str = DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
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
        self.title = title or (self.note[:30] if self.note else "")
        self.tags = tags or []

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")
        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        if len(self.image_paths) > 35:
            raise ValueError("图文模式下最多只支持上传 35 张图片")

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        douyin_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))
        douyin_logger.info(_msg("🔀", "小人正在切换到图文发布"))
        await page.get_by_text("发布图文", exact=True).click()
        await page.wait_for_timeout(1000)

        douyin_logger.info(_msg("📤", "小人正在上传图片"))
        await page.locator("div[class^='container'] input[accept*='image']").set_input_files(self.image_paths)

        while True:
            try:
                await page.wait_for_url(
                    "**/creator-micro/content/post/image?**",
                    timeout=3000,
                )
                douyin_logger.info(_msg("🥳", "已经进入图文发布页面"))
                break
            except Exception:
                douyin_logger.debug(_msg("🧍", "小人还在等图片上传完成"))
                await asyncio.sleep(0.5)

        await asyncio.sleep(1)
        douyin_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_title_and_description(page, self.title, self.note, self.tags)
        douyin_logger.info(_msg("🏷️", f"小人一共贴了 {len(self.tags)} 个话题"))

        if self.publish_strategy == DOUYIN_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_douyin(page, self.publish_date)

        while True:
            try:
                publish_button = page.get_by_role("button", name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url(
                    "**/creator-micro/content/manage?enter_from=publish**",
                    timeout=3000,
                )
                douyin_logger.success(_msg("🥳", "图文发布成功，小人开心收工"))
                break
            except Exception:
                douyin_logger.info(_msg("🏃", "小人正在冲刺发布图文"))
                await asyncio.sleep(0.5)

    async def upload(self, playwright: Playwright) -> None:
        douyin_logger.info(_msg("🧍", "小人先检查 cookie、图片和发布时间"))
        await self.validate_upload_args()
        douyin_logger.info(_msg("🥳", "图文上传前检查通过"))

        browser = await playwright.chromium.launch(headless=self.headless, channel="chrome")
        context = await browser.new_context(
            storage_state=f"{self.account_file}",
            permissions=["geolocation"],
        )
        context = await set_init_script(context)

        upload_success = False
        try:
            page = await context.new_page()
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            douyin_logger.info(_msg("🧭", "小人正在赶往图文发布页"))
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")

            await self.upload_note_content(page)
            upload_success = True
        finally:
            if upload_success:
                await context.storage_state(path=self.account_file)
                douyin_logger.success(_msg("🥳", "cookie 更新完毕"))
                await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def douyin_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
