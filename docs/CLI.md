# CLI 使用说明

> 当前推荐使用 Web 管理台。本文件说明保留的兼容入口，其功能未随本次 Web 更新同步维护；使用前需核对实际代码，不应将参数或帮助检查通过视为平台流程可用。

OmniPost 提供统一 CLI 入口 `sau`，当前已接入：

- `douyin`
- `kuaishou`
- `xiaohongshu`
- `bilibili`
- `tencent`（视频号）

实现说明：

- `sau_cli.py` 是当前 CLI 的主入口和唯一主要实现文件
- `sau.exe` 是安装后在 Windows 虚拟环境里自动生成的命令入口，本质上还是调用 `sau_cli.py`
- 如果需要给 OpenClaw、Codex 等 agent 使用，可参考仓库内 skill：
  - `skills/douyin-upload/`
  - `skills/kuaishou-upload/`
  - `skills/xiaohongshu-upload/`
  - `skills/bilibili-upload/`

## 安装 CLI 入口

首次安装按 [README](../README.md#安装) 复制配置、安装依赖和准备浏览器。仅使用 CLI 时，依赖命令为：

```bash
uv sync --locked --python 3.12
uv run --no-sync sau --help
```

下文命令在源码根目录执行，无需激活环境。已激活 `.venv` 或 `sau` 已在 PATH 中时，可以简写为 `sau ...`。素材路径、账号名和定时时间均需替换；命令参数以实际 `--help` 为准。入口覆盖与已验证范围见 [项目状态](./status.md)。

## 浏览器要求

主要浏览器上传模块使用系统 Google Chrome 稳定版。安装 `patchright` 的 Chromium 不能替代 Chrome。Web 的部分账号校验和旧示例还需要 `uv run --no-sync playwright install chromium`，详见 README。

## 抖音 CLI 子命令

```bash
uv run --no-sync sau douyin login --account <account_name>
uv run --no-sync sau douyin login --account <account_name> --headless
uv run --no-sync sau douyin check --account <account_name>
uv run --no-sync sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 运动,训练
uv run --no-sync sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

## 快手 CLI 子命令

```bash
uv run --no-sync sau kuaishou login --account <account_name>
uv run --no-sync sau kuaishou check --account <account_name>
uv run --no-sync sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 运动,训练
uv run --no-sync sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

## 小红书 CLI 子命令

```bash
uv run --no-sync sau xiaohongshu login --account <account_name>
uv run --no-sync sau xiaohongshu check --account <account_name>
uv run --no-sync sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tags 小红书,视频
uv run --no-sync sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --tags 图文,测试
```

## Bilibili CLI 子命令

```bash
uv run --no-sync sau bilibili login --account <account_name>
uv run --no-sync sau bilibili check --account <account_name>
uv run --no-sync sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249 --tags 足球,测试
```

补充说明：

- `creator` 之类的名字只是示例值，真正传的是用户自定义的 `account_name`
- 一个 `account_name` 对应一个账号文件，可以准备多个账号并发使用
- 浏览器平台统一元数据约定：
- 视频使用 `title + desc + tags`
- 图文使用 `title + note + tags`
- `sau bilibili ...` 会自动准备 `biliup`
- 如果本地没有 `biliup`，第一次运行会自动下载
- 如果上游 GitHub Release 有更新，运行时会先自动更新
- `sau bilibili login --account <name>` 建议由用户自己在本地真实终端里执行；如果终端里的二维码显示不完整，可直接打开当前目录下的 `qrcode.png` 扫码

## 视频号 CLI 子命令

```bash
uv run --no-sync sau tencent login --account <account_name>
uv run --no-sync sau tencent check --account <account_name>
uv run --no-sync sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
uv run --no-sync sau tencent upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --draft
```

视频号提供 `login`、`check` 和 `upload-video`，没有 `upload-note`。视频可选 `--short-title`、`--category`、`--thumbnail`、`--schedule`；`--draft` 表示保存草稿。视频号暂无独立 Skill。

## 登录二维码说明

- 抖音、快手、小红书登录过程中，CLI / uploader 可能会生成临时二维码图片
- 对普通用户来说，可以直接打开该图片扫码
- 对可操作本地文件的 agent 来说，不要只把图片路径告诉用户
- 这类二维码图片本身就是给用户扫码的，agent 应优先直接展示/发送本地图片给用户
- Bilibili 当前不走这套本地二维码图片托管链路，登录按上面的 Bilibili CLI 说明处理即可

## 定时发布

示例中的 `YYYY-MM-DD HH:MM` 必须替换为符合平台限制的未来本地时间。不要直接执行占位时间。

抖音、快手、小红书的图文和视频上传，以及 Bilibili、视频号的视频上传都支持 `--schedule`。只要传了 `--schedule`，CLI 就会自动切换到对应平台的定时发布策略；不传则默认立即发布。

```bash
uv run --no-sync sau douyin upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau douyin upload-note --account <account_name> --images videos/1.png videos/2.png --title "图文标题" --note "图文示例" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau kuaishou upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau kuaishou upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau xiaohongshu upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau xiaohongshu upload-note --account <account_name> --images videos/1.png videos/2.png videos/3.png --title "图文标题" --note "图文示例" --schedule "YYYY-MM-DD HH:MM"
uv run --no-sync sau bilibili upload-video --account <account_name> --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249 --schedule "YYYY-MM-DD HH:MM"
```

## 运行时参数

CLI 将 `debug` 和 `headless` 拆成了两个独立维度：

```bash
--debug
--headless
--headed
```

- `--debug`: 打开调试行为，例如失败时保留更多调试信息
- `--headless`: 无头模式运行
- `--headed`: 有头模式运行

浏览器平台（抖音、快手、小红书、视频号）不传时默认按 `headless=True` 运行。Bilibili 通过 biliup 执行，不提供这些浏览器参数。

补充：

- 抖音和快手的 CLI 默认都是无头模式
- 如果用户明确要求可见浏览器窗口，或确实需要人工看页面，再显式传 `--headed`

## 视频上传参数

各平台参数并不完全相同：下列 `--thumbnail` 用于浏览器平台，Bilibili 没有该参数；具体必填项以对应命令的 `--help` 为准。

```bash
--file videos/demo.mp4
--title "示例标题"
--desc "示例简介"
--tags 运动,训练
--thumbnail videos/demo.png
```

抖音额外支持：

```bash
--product-link https://example.com/item
--product-title 示例商品
```

Bilibili 额外要求：

```bash
--tid 249
```

- `--tid` 和 `--desc` 均必填
- `--tags` 会映射到 `biliup upload --tag`
- `--schedule` 会映射到 Bilibili 所需的时间戳参数

## 图文上传参数

```bash
--images videos/1.png videos/2.png videos/3.png
--title "图文标题"
--note "图文内容"
--tags 图文,测试
```

图文上传当前限制：

- 抖音：最多 35 张图片，不支持 GIF
- 快手：支持多张图片，建议传真实不同文件，不要把同一路径重复多次
- 小红书：支持多张图片，正文 `--note` 可选，但 `--title` 建议始终显式传入

后续维护 CLI 时，优先看 `sau_cli.py`、`uploader/` 和 `skills/`。
