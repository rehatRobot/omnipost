# OmniPost Web 前端

这是 OmniPost 的本地管理台，使用 Vue 3、Vite、Element Plus、Pinia、Vue Router 和 Axios。完整安装和启动以 [根目录 README](../README.md#安装) 为准，验证范围见 [项目状态](../docs/status.md)。

## 页面与目录

| 页面 | 文件 |
| --- | --- |
| 首页 | `src/views/Dashboard.vue` |
| 账号管理 | `src/views/AccountManagement.vue` |
| 创作者中心 | `src/views/CreatorCenter.vue` |
| 素材管理 | `src/views/MaterialManagement.vue` |
| 发布中心 | `src/views/PublishCenter.vue` |
| 数据中心 | `src/views/DataCenter.vue` |
| 关于 | `src/views/About.vue` |

API 封装在 `src/api/`，请求工具在 `src/utils/request.js`，路由在 `src/router/index.js`，状态在 `src/stores/`。路由使用 Hash 模式。

## 常用命令

以下命令均从项目根目录执行，前端需要 Node.js 22 或 24：

```bash
npm --prefix sau_frontend ci
npm --prefix sau_frontend run dev -- --strictPort
npm --prefix sau_frontend run build
npm --prefix sau_frontend run preview -- --strictPort
```

开发服务默认仅监听 `127.0.0.1:5173`；构建预览默认仅监听 `127.0.0.1:4173`。后端需按根目录 README 在另一个终端启动。预览命令需要先完成构建。

## API 配置

- 开发环境通过 `.env.development` 的 `/api` 前缀代理到 `127.0.0.1:5409`。
- `.env.production` 默认指向本机后端；构建静态文件不会同时启动后端。
- 扫码登录 SSE 在开发环境直接连接本机后端；后端允许本机来源跨域。
- Axios 会附带本地保存的 Token，但当前后端没有完整的登录鉴权机制；不能据此宣称服务提供了身份认证。

平台覆盖和发布参数见 [Web 说明](../docs/legacy-web.md) 与 [后端接口说明](../sau_backend/README.md)。前端构建成功不代表平台发布成功。
