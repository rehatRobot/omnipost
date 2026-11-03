# 更新说明

本次更新以 Web 界面及其后端流程为主。首次安装见 [README](../README.md#安装)，排障见 [安装说明](./install.md)，当前能力和验证范围见 [项目状态](./status.md)。

## 同步代码与依赖

先停止正在运行的前后端，并保留本地配置、Cookie、数据库和素材。Git 用户在自己的源码根目录拉取更新：

```bash
git pull
uv sync --locked --extra web --python 3.12
npm --prefix sau_frontend ci
uv run --no-sync python db/createTable.py
```

纯 CLI 用户可去掉 `--extra web`，并跳过前端安装和数据库初始化。使用源码 ZIP 的用户应解压新源码，迁移所需的本地配置和数据；不要对没有 `.git` 的目录执行 `git pull`。

普通更新使用仓库提供的锁文件，不需要执行 `uv lock` 或重新生成 `package-lock.json`。数据库初始化会创建缺少的表和运行目录，不会删除已有记录；它不等同于任意版本之间的完整数据迁移工具。

浏览器驱动版本变化时，按 README 检查 Chrome，并更新 Web 校验所需的 Chromium：

```bash
uv run --no-sync playwright install chromium
```

如果使用自定义 `PLAYWRIGHT_BROWSERS_PATH`，安装和运行时保持一致。

## 更新后检查

```bash
uv run --no-sync sau --help
uv run --no-sync sau douyin --help
uv run --no-sync sau kuaishou --help
uv run --no-sync sau xiaohongshu --help
uv run --no-sync sau bilibili --help
uv run --no-sync sau tencent --help
```

Web 用户再运行 `npm --prefix sau_frontend run build`，并按 README 在两个终端启动服务，检查首页和基础接口。默认地址为 `http://127.0.0.1:5173/`，后端仅监听 `127.0.0.1:5409`。

CLI 帮助和 Web 页面检查无需真实平台登录。账号校验、上传、发布与数据同步应在用户明确指定账号和操作后单独验证，并记录具体平台、入口和结果。

使用 Skill 的用户应同步对应的 `skills/<platform>-upload/` 整个目录，并核对命令契约。当前维护和推荐入口为 Web；CLI、examples 和 Skill 未随本次 Web 更新同步维护，仅保留供兼容与开发参考。
