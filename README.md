# OmniPost

**OmniPost** 是多平台自媒体内容自动发布工具，**推荐通过 Web 管理台使用**，在浏览器中完成账号管理、素材上传、内容发布和数据查看。

> 当前更新以 **Web 界面及其后端流程** 为主。CLI、examples 和 Skill 保留供兼容与开发参考，**功能尚未随本次 Web 更新同步维护**，不作为当前推荐使用方式。

> 本仓库基于开源项目 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) 二开。感谢原作者与社区贡献者。

## 目录

- [功能特性](#功能特性)
- [架构概览](#架构概览)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [平台能力](#平台能力)
- [配置说明](#配置说明)
- [文档索引](#文档索引)
- [AI Agent](#ai-agent)
- [免责声明](#免责声明)
- [贡献](#贡献)
- [致谢](#致谢)
- [许可证](#许可证)

## 功能特性

当前维护和推荐入口为 **Web 管理台**。下列功能按 Web 实现描述，真实平台发布的验证范围见 [项目状态](./docs/status.md)。

- **多平台发布**：抖音、B 站、小红书、快手、视频号、百家号、今日头条、搜狐号、知乎、TikTok 等
- **视频与文章**：部分平台提供文章发布入口，具体见 Web 能力表
- **账号与 Cookie 管理**：通过界面扫码登录、导入或导出 Cookie
- **定时发布**：多数平台支持（以各平台后台能力为准）
- **Web 发布中心**：选择账号与素材，配置内容、预览并查看发布任务结果
- **可扩展 uploader**：每个平台独立模块，便于二开接入新平台

适合通过本地 Web 界面集中处理多账号内容发布，减少重复上传和填表操作。实际发布结果仍需按平台和账号验证。

## 架构概览

| 部分 | 说明 |
| --- | --- |
| `sau_backend.py` | Flask API：账号、素材、发布任务 |
| `sau_frontend/` | Vue3 + Element Plus 管理台（账号 / 素材 / 发布中心） |
| `uploader/*` | 各平台 Playwright / 专用运行时上传实现 |
| `sau_cli.py` | 保留的 CLI 入口，未随本次 Web 更新同步维护 |
| `examples/` | 保留的单平台示例，使用前需自行核对当前实现 |
| `skills/` | 保留的 CLI Skill 参考，未随本次 Web 更新同步维护 |
| `db/` | SQLite 账号与文件元数据 |

## 环境要求

- Python **3.10–3.12**，推荐 **3.12**（暂不支持 3.13 及以上）
- Node.js **22 或 24** 与 npm（仅 Web 前端需要）
- `uv`：运行 `uv --version` 确认可用；已有 Python 时可用 `python -m pip install --upgrade uv` 安装
- **Google Chrome 稳定版**：主要上传模块使用 `channel="chrome"`；仅安装 Chromium 不能替代 Chrome
- Windows / macOS / Linux；下文的本地安装流程已在 Windows + Python 3.12 验证

## 安装

以下为推荐的 **Web 管理台安装流程**，所有命令均在项目根目录执行。Python 依赖以 `pyproject.toml` 和 `uv.lock` 为准，前端依赖以 `package-lock.json` 为准。无需激活虚拟环境。

### 1. 获取源码

```bash
git clone https://github.com/rehatRobot/omnipost.git
cd omnipost
```

下载 ZIP 的用户先解压，再进入包含 `pyproject.toml` 的目录。

### 2. 创建本地配置

首次安装时复制配置；已有 `conf.py` 时保留原文件。

Windows PowerShell：

```powershell
if (-not (Test-Path conf.py)) { Copy-Item conf.example.py conf.py }
```

macOS / Linux：

```bash
test -f conf.py || cp conf.example.py conf.py
```

标准安装的 Chrome 可以保留 `LOCAL_CHROME_PATH = ""`。Chrome 安装在其他位置时，按需设置 `conf.py`，例如 `LOCAL_CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe"`。部分 CLI 流程固定使用系统 Chrome，仍需安装 Chrome 稳定版。

### 3. 安装锁定的 Python 依赖

```bash
uv sync --locked --extra web --python 3.12
```

这会创建 `.venv`，并安装 Web、CLI 和上传模块需要的依赖。`uv` 找不到 Python 3.12 时可能下载解释器，因此首次安装需要联网。

`requirements.txt` 只保留兼容入口，`pip install -r requirements.txt` 不提供锁定版本安装；推荐使用上面的 `uv sync`。

### 4. 安装 Web 账号校验使用的 Chromium

主要上传模块使用系统 Chrome；Web 的部分账号校验和旧示例还会使用 Playwright Chromium，需要另外安装：

```bash
uv run --no-sync playwright install chromium
```

Linux 缺少浏览器系统库时，改用 `uv run --no-sync playwright install --with-deps chromium`，系统依赖安装可能需要管理员权限。

### 5. 初始化数据库

```bash
uv run --no-sync python db/createTable.py
```

初始化会创建 `db/database.db`、`cookies/`、`cookiesFile/` 和 `videoFile/`。脚本可以从任意工作目录运行，重复执行保留已有数据，无需删除数据库。

### 6. 安装前端依赖

```bash
npm --prefix sau_frontend ci
```

`npm ci` 使用随源码发布的锁文件。

### 7. 启动 Web 前后端

在项目根目录打开两个终端，分别运行：

```bash
# 终端 1：后端，默认 http://127.0.0.1:5409
uv run --no-sync python sau_backend.py
```

```bash
# 终端 2：前端
npm --prefix sau_frontend run dev -- --host 127.0.0.1 --strictPort
```

浏览器打开 **http://127.0.0.1:5173/**。后端、前端开发服务和构建预览默认仅监听 `127.0.0.1`，局域网中的其他设备无法直接访问；后端跨域请求仅允许 `localhost` 和 `127.0.0.1` 来源。前端首页、账号管理和素材管理应能正常加载；新安装时账号和素材列表为空。两个终端中分别按 `Ctrl+C` 停止服务。

Windows 完成首次安装后，也可以双击 `start-win.bat`；它会检查依赖、初始化目录和数据库，再打开前后端终端。关闭这两个服务终端即可停止服务。

更多排障说明见 [安装说明](./docs/install.md)。不要公开 `conf.py`、Cookie、数据库和 `logs/`。

## 快速开始

完成安装并启动前后端后，打开 **http://127.0.0.1:5173/**：

1. 在「账号管理」添加平台账号，完成扫码登录或导入 Cookie。
2. 在「素材管理」上传视频、封面等素材。
3. 在「发布中心」选择平台、账号与素材，填写标题、标签或文章正文。
4. 按需选择预览、立即发布或平台支持的定时发布方式。
5. 在发布记录中检查最终结果；需要查看运营数据时进入「数据中心」。

新安装时账号和素材列表为空。任务提交成功不代表平台发布成功；真实发布的验证范围见 [项目状态](./docs/status.md)。

### 其他入口（未同步更新）

CLI、示例脚本和 Skill 仍保留在源码中，供已有使用者或开发者参考。本次更新不保证这些入口与 Web 功能一致，使用前需自行核对参数和平台流程：

- [CLI 参考](./docs/CLI.md)
- [示例脚本](./examples/)
- [CLI Skill 分发参考](./docs/skill-distribution.md)

## 平台能力

下表仅描述 **Web 管理台的代码接线范围**。✅ 表示已有实现，❌ 表示 Web 当前没有对应入口；**不代表已完成真实账号发布验证**。保留的 CLI / examples 能力不计入此表。

| 平台 | 视频 | 文章 | 备注 |
| --- | --- | --- | --- |
| 抖音 | ✅ | ❌ | 当前 Web 发布视频 |
| Bilibili | ✅ | ❌ | 通过 biliup 执行 |
| 小红书 | ✅ | ❌ | 当前 Web 发布视频 |
| 快手 | ✅ | ❌ | 当前 Web 发布视频 |
| 视频号 | ✅ | ❌ | 当前 Web 发布视频 |
| 百家号 | ✅ | ✅ | 视频与文章入口 |
| 今日头条 | ✅ | ✅ | 文章入口，不含微头条 |
| 搜狐号 | ❌ | ✅ | 当前仅文章 |
| 知乎 | ❌ | ✅ | 当前仅文章 |

TikTok 的实现保留在 uploader / examples 中，尚未接入 Web 发布中心。平台后台、账号权限或风控变化可能影响自动化，定时发布等选项以各平台实现为准。入口详情见 [Web 说明](./docs/legacy-web.md)，本地检查与未实测范围见 [项目状态](./docs/status.md)。

## 配置说明

- 配置模板：[`conf.example.py`](./conf.example.py) → 复制为 `conf.py`
- Cookie 目录：`cookies/`（CLI / 示例）与 `cookiesFile/`（Web 账号）
- Web 素材目录：`videoFile/`
- 日志：`logs/`

开源或分享仓库前请确认敏感文件已被忽略，可参考 [`.gitignore`](./.gitignore)。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [docs/status.md](./docs/status.md) | 项目定位、入口覆盖与验证状态 |
| [docs/install.md](./docs/install.md) | 安装排障 |
| [docs/update.md](./docs/update.md) | 更新说明 |
| [docs/CLI.md](./docs/CLI.md) | `sau` CLI |
| [docs/agent-bootstrap.md](./docs/agent-bootstrap.md) | 交给 AI Agent 的启动提示词 |
| [docs/legacy-web.md](./docs/legacy-web.md) | Web 版本说明与验证范围 |
| [skills/*/SKILL.md](./skills) | 各平台 Agent Skill |

## AI Agent

需要 Agent 协助时，推荐先让它按 [启动提示词](./docs/agent-bootstrap.md) 完成 Web 环境安装、启动和基础页面检查。

请明确要求优先使用当前 Web 界面及其后端流程。CLI 和四个已有 Skill 属于未同步更新的兼容参考；只有明确需要这些入口时，再核对对应代码和参数。

## 免责声明

- 本项目仅供学习、研究与个人效率提升使用。  
- 使用自动化发布可能违反部分平台用户协议，存在账号限制、验证码、功能不可用等风险，**后果由使用者自行承担**。  
- 请勿用于垃圾信息、违规内容分发或其他违法用途。  
- 平台页面与接口随时变更，不保证某一功能长期可用。

## 贡献

欢迎 Issue / PR：

1. Fork 本仓库  
2. 新建分支：`feature/xxx` 或 `fix/xxx`  
3. 提交清晰的变更说明  
4. 发起 Pull Request  

建议：改动平台自动化时附上复现步骤、脱敏后的日志片段（来自 `logs/`）与是否 dry-run。

## 致谢

- 原项目：[dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)
- B 站上传能力基于 [biliup](https://github.com/biliup/biliup) 的接入与封装
- 所有提交 Issue、PR 与反馈的贡献者

## 许可证

本项目采用 [MIT License](./LICENSE)。

使用或二次发布时，请保留许可证与版权声明，并保留对上游项目与 `biliup` 的致谢信息。
