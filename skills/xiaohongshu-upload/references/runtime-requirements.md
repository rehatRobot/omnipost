# 运行前提

此 Skill 操作 OmniPost 的 `xiaohongshu` CLI。项目名称为 OmniPost，Python 包名仍为 `social-auto-upload`，CLI 命令为 `sau`。

## 源码环境

在 OmniPost 源码根目录按 README 复制 `conf.example.py` 为 `conf.py`（保留已有配置），再执行：

```bash
uv sync --locked --python 3.12
uv run --no-sync sau xiaohongshu --help
```

Python 支持 3.10–3.12，推荐 3.12。Web 管理台另需 `--extra web` 和前端安装，完整步骤以源码 README 为准。单独复制 Skill 不会安装项目或运行依赖。

本 Skill 的命令契约中使用 `sau ...` 简写。可在已激活 `.venv` 或 `sau` 已在 PATH 的环境直接调用；在源码根目录、未激活环境时使用 `uv run --no-sync sau ...`。从仓库外调用前，先进入正确的源码目录或定位已安装的可执行文件。

## 浏览器

主要上传流程使用系统 Google Chrome 稳定版。仅安装 patchright Chromium 不能替代 `channel="chrome"` 使用的系统 Chrome。Web 的部分账号校验和旧示例另外使用 Playwright Chromium，按源码 README 准备。

CLI 默认无头运行，`--headed` 可打开可见窗口，`--headless` 明确指定无头模式。登录若生成二维码图片，可展示该图片给用户扫码。
