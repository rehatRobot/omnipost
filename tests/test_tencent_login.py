import asyncio
import unittest
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from myUtils import login


class _FakeImage:
    async def wait_for(self, state=None, timeout=None):
        pass

    async def get_attribute(self, name):
        self.requested_attribute = name
        return "/connect/qrcode/qr"


class _FakeImageLocator:
    def __init__(self):
        self.first = _FakeImage()


class _FakeFrameLocator:
    first = None

    def __init__(self):
        self.first = self
        self.image = _FakeImageLocator()

    def get_by_role(self, role):
        return self.image

    async def wait_for(self, state=None, timeout=None):
        pass


class _FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.main_frame = object()
        self.frame = _FakeFrameLocator()
        self.wait_for_url = AsyncMock()
        self.wait_for_timeout = AsyncMock()

    async def goto(self, url, **kwargs):
        self.url = url

    def on(self, event, callback):
        self.url += "?logged-in"
        callback(self.main_frame)

    def frame_locator(self, selector):
        return self.frame

    def locator(self, selector):
        return self.frame

    async def close(self):
        pass


class _FakeContext:
    def __init__(self):
        self.page = _FakePage()

    async def new_page(self):
        return self.page

    async def storage_state(self, path):
        Path(path).write_text("{}", encoding="utf-8")

    async def close(self):
        pass


class _FakeBrowser:
    def __init__(self):
        self.context = _FakeContext()

    async def new_context(self):
        return self.context

    async def close(self):
        pass


class _FakeChromium:
    def __init__(self):
        self.launch_options = None
        self.browser = _FakeBrowser()

    async def launch(self, **options):
        self.launch_options = options
        return self.browser


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


class _PlaywrightContext:
    def __init__(self, playwright):
        self.playwright = playwright

    async def __aenter__(self):
        return self.playwright

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TencentLoginTests(unittest.TestCase):
    def test_browser_options_use_chrome_channel_without_explicit_path(self):
        with patch.object(login, "LOCAL_CHROME_PATH", ""):
            options = login.get_browser_options()

        self.assertEqual(options["channel"], "chrome")
        self.assertNotIn("executable_path", options)

    def test_video_account_login_uses_configured_chrome_and_emits_qr(self):
        fake_playwright = _FakePlaywright()
        with TemporaryDirectory() as td:
            with patch.object(login, "BASE_DIR", Path(td)), \
                    patch.object(login, "LOCAL_CHROME_PATH", "C:/Chrome/chrome.exe"), \
                    patch.object(login, "LOCAL_CHROME_HEADLESS", False), \
                    patch.object(login, "async_playwright", return_value=_PlaywrightContext(fake_playwright)), \
                    patch.object(login, "set_init_script", new=AsyncMock(side_effect=lambda context: context)), \
                    patch.object(login, "check_cookie", new=AsyncMock(return_value=True)), \
                    patch.object(login.sqlite3, "connect") as connect:
                conn = connect.return_value.__enter__.return_value
                queue = Queue()
                asyncio.run(login.get_tencent_cookie("测试视频号", queue))

        self.assertEqual(fake_playwright.chromium.launch_options["executable_path"], "C:/Chrome/chrome.exe")
        self.assertFalse(fake_playwright.chromium.launch_options["headless"])
        self.assertEqual(queue.get_nowait(), "https://open.weixin.qq.com/connect/qrcode/qr")
        self.assertEqual(queue.get_nowait(), "200")
        fake_playwright.chromium.browser.context.page.wait_for_url.assert_awaited_once_with(
            "**/platform/**", wait_until="commit", timeout=30_000
        )
        fake_playwright.chromium.browser.context.page.wait_for_timeout.assert_awaited_once_with(2000)
        conn.cursor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
