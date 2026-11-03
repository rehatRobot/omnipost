# Agent 启动提示词

OmniPost 当前维护和推荐使用的是 **Web 界面及其后端流程**。CLI、examples 和 Skill 保留供兼容与开发参考，功能未随本次 Web 更新同步维护。项目定位与验证范围见 [项目状态](./status.md)。

## 可复制的提示词

```text
你正在 OmniPost 源码目录中工作。请优先帮助我安装、启动和使用 Web 管理台。

先读取 README.md 的 Web 安装章节、docs/install.md 和 docs/status.md。
CLI、examples 和 Skill 未随本次 Web 更新同步维护，不要默认转用这些入口。
只有我明确要求使用其他入口时，再核对对应实现、参数和实际可用性。

保留已有 conf.py；首次安装才从 conf.example.py 复制。
使用 uv sync --locked --extra web --python 3.12 安装 Python 依赖。
按 README 准备系统 Chrome 和 Web 账号校验需要的 Playwright Chromium。
使用 uv run --no-sync python db/createTable.py 初始化，不要删除已有数据库。
使用 npm --prefix sau_frontend ci 安装前端依赖。
按 README 在两个终端启动后端与前端，打开 http://127.0.0.1:5173/。
保持服务默认仅本机访问，验证结束后关闭你启动的测试服务。

安装验证优先检查首页、账号管理、素材管理、发布中心、数据中心及基础账号/素材接口。
不要为了验证安装而擅自登录或发布真实内容；需要账号和素材时说明具体缺少什么。
我要求登录时，若界面或流程生成二维码，可展示给我扫码。
完成后报告实际修改、检查结果和未实测项。
不要把依赖安装成功、页面渲染、dry-run 或任务提交成功描述为真实发布成功。
```

## 后续任务示例

- “启动本机 Web 管理台，检查账号和素材页面。”
- “在 Web 账号管理中添加我指定的平台账号，准备二维码让我扫码。”
- “检查我上传的素材和文案，按指定账号与时间配置 Web 发布任务。”
- “查看发布记录，区分任务提交、执行中和最终发布结果。”

使用 CLI 或 Skill 的兼容任务应单独说明，不能据此推断它们与本次 Web 更新保持一致。
