# 安装与排障

当前推荐使用 Web 管理台；CLI、examples 和 Skill 未随本次 Web 更新同步维护，相关说明仅供兼容参考。项目定位与验证范围见 [项目状态](./status.md)。完整安装命令统一维护在 [README 的安装章节](../README.md#安装)。请从该章节依次执行配置复制、`uv sync --locked --extra web --python 3.12`、浏览器安装、数据库初始化、`npm ci` 和前后端启动。

## 安装约定

- 进入包含 `pyproject.toml` 的源码根目录；下载 ZIP 后先解压。
- 使用 Python 3.10–3.12，推荐 3.12；Node.js 使用 22 或 24。
- 先复制 `conf.example.py` 为 `conf.py`，再安装项目。不要覆盖已有配置。
- `uv sync --locked --extra web --python 3.12` 负责创建 `.venv` 并安装依赖，无需手动激活。
- 仅使用 CLI：`uv sync --locked --python 3.12`，无需 Node.js 和前端依赖。
- 后续命令使用 `uv run --no-sync`，避免无意同步为不含 Web 依赖的环境。
- `uv.lock` 与 `sau_frontend/package-lock.json` 都需要随源码发布；普通安装不要重新生成锁文件。
- `requirements.txt` 是指向 `.[web]` 的 pip 兼容入口，不作为锁定安装方式。
- 后端（5409）、前端开发服务（5173）和构建预览（4173）默认仅监听 `127.0.0.1`；后端仅向本机来源提供跨域响应头。容器内的 `127.0.0.1` 属于容器本身，默认启动方式不提供容器端口映射访问。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 找不到 `uv` | 用可用的 Python 执行 `python -m pip install --upgrade uv`，重新打开终端并检查 `uv --version` |
| Python 版本不受支持 | 使用 README 中的 `--python 3.12`，不要用 Python 3.13+ 创建环境 |
| `No module named conf` | 在项目根目录复制配置模板；不要在未解压的 ZIP 中运行 |
| 缺少 Flask、xhs、Playwright 等模块 | 在根目录重新执行 `uv sync --locked --extra web --python 3.12`，并使用 `uv run --no-sync` 启动 |
| 找不到 `sau` | 使用 `uv run --no-sync sau --help`，无需全局安装或激活虚拟环境 |
| `no such table: user_info` | 在根目录执行 `uv run --no-sync python db/createTable.py`；重复初始化不会删除账号 |
| 上传提示目录不存在 | 重新运行数据库初始化脚本，它会创建 Cookie 和素材目录 |
| 找不到 Chrome | 安装 Google Chrome 稳定版；`playwright install chromium` 不会安装 `channel="chrome"` 使用的 Chrome |
| 找不到 Playwright Chromium | 执行 `uv run --no-sync playwright install chromium`；Linux 可加 `--with-deps` 安装系统库 |
| 浏览器安装长时间无输出 | 检查是否有其他安装进程或旧缓存锁；不要同时运行多个浏览器安装。受限环境可通过 `PLAYWRIGHT_BROWSERS_PATH` 指定可写缓存目录，但安装和后续运行必须使用相同设置 |
| npm 提示没有锁文件 | 确认使用当前完整源码，其中应包含 `sau_frontend/package-lock.json` |
| 前端提示接口连接失败 | 确认后端终端没有异常，访问 `http://127.0.0.1:5409/getAccounts` 应返回 `code: 200` |
| 5173 端口占用 | 停止已有前端，或传入 `--port 5174` 并使用终端输出的新地址 |
| 5409 端口占用 | 停止已有后端，不要重复启动；Windows 可用 `Get-NetTCPConnection -LocalPort 5409 -State Listen` 查看 |
| 下载超时 | 检查代理与网络。可通过 uv 的 `--index-url` 或 npm 的 `--registry` 临时指定可信镜像，不要删除锁文件绕过错误 |

## 使用独立浏览器缓存

如果默认浏览器缓存因旧锁或目录权限导致安装停滞，可以使用项目内的可写目录。先进入项目根目录，再在同一个终端中设置环境变量、安装浏览器和启动后端。

Windows PowerShell：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.uv-cache/playwright-browsers'
uv run --no-sync playwright install chromium
uv run --no-sync python sau_backend.py
```

macOS / Linux：

```bash
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.uv-cache/playwright-browsers"
uv run --no-sync playwright install chromium
uv run --no-sync python sau_backend.py
```

每次开启新的后端终端都需要重新设置该变量；使用此方案时，从设置过变量的终端启动服务。前端可以在另一个终端运行。`.uv-cache/` 不收入开源包。

## 如何确认安装成功

1. `uv run --no-sync sau --help` 能输出 CLI 帮助。
2. 初始化脚本显示数据库位于项目的 `db/database.db`。
3. 后端启动后，`http://127.0.0.1:5409/getAccounts`、`http://127.0.0.1:5409/getFiles` 返回 `code: 200`。
4. 打开 `http://127.0.0.1:5173/`，首页、账号管理、素材管理可加载。
5. 可选构建检查：`npm --prefix sau_frontend run build`。

这些检查验证安装和本地 Web 链路。真实平台登录、上传与定时发布仍需要对应账号、网络条件及平台权限。

## CLI 与 AI Agent

CLI 用法见 [CLI 文档](./CLI.md)，Agent 入口见 [启动提示词](./agent-bootstrap.md)。使用 CLI 时同样通过 `uv run --no-sync sau ...` 调用。

Bilibili 首次相关命令可能下载 `biliup`，需要访问其发布地址；登录建议由用户在本地真实终端执行。登录二维码和 Cookie 属于本地运行数据，不应收入公开源码。
