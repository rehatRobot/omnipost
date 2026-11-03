# OmniPost 后端接口说明

实际后端入口是项目根目录的 `sau_backend.py`；本目录用于保存说明，不是单独的后端应用。安装和启动统一见 [README](../README.md#安装)，能力与验证状态见 [项目状态](../docs/status.md)。

后端默认仅监听 `127.0.0.1:5409`，跨域来源只允许 `localhost` 和 `127.0.0.1`。当前没有完整身份认证机制。

## 平台类型

| type | 平台 |
| --- | --- |
| 1 | 小红书 |
| 2 | 视频号 |
| 3 | 抖音 |
| 4 | 快手 |
| 5 | 百家号 |
| 6 | Bilibili |
| 7 | 今日头条 |
| 8 | 搜狐号 |
| 9 | 知乎 |

各入口支持范围见 [Web 说明](../docs/legacy-web.md)。TikTok 当前不接入此 Web 平台类型表。

## 常用接口

| 方法与路径 | 用途 |
| --- | --- |
| `GET /getAccounts` | 快速获取账号，不校验 Cookie |
| `GET /getValidAccounts` | 校验账号 Cookie；可用 `type` 限定平台，可能较慢 |
| `GET /login?type=...&id=...` | SSE 扫码登录，`id` 为用户指定账号名 |
| `POST /upload` | 上传文件，返回存储文件名 |
| `POST /uploadSave` | 上传素材并保存数据库记录，使用 multipart 文件字段 `file` |
| `GET /getFiles` | 素材列表 |
| `GET /getFile?filename=...` | 素材预览 |
| `POST /postVideo` | 提交视频或受支持平台的文章任务 |
| `GET /publishJob/<job_id>` | 查询任务及逐账号、逐素材结果 |
| `POST /postVideoBatch` | 批量发布入口，具体结构以路由实现为准 |
| `POST /openCreatorCenter` | 使用已保存的账号打开创作者中心 |
| `POST /uploadCookie`、`GET /downloadCookie` | Cookie 导入、导出 |
| `GET /getContentStats`、`POST /syncContentStats` | 内容统计读取与同步 |
| `POST /pushContentStatsToDingTalk` | 推送统计到配置的钉钉机器人 |

接口返回通常使用 `code`、`msg`、`data`；应同时检查 HTTP 状态和业务状态。返回的 Cookie 与导出文件应作为登录凭证保存。

## 发布字段

以下名称与当前 `/postVideo` 的 JSON 字段一致，不能替换成旧文档的下划线字段。

| 字段 | 说明 |
| --- | --- |
| `type` | 上表中的平台编号 |
| `fileList` | 视频素材的存储文件名列表；文章使用下面的文章字段 |
| `accountList` | 账号列表接口中 `filePath` 对应的 Cookie 文件名列表 |
| `title`、`tags` | 标题及标签列表，限制因平台而异 |
| `contentType` | `video` 或 `article`；文章入口用于百家号、今日头条、搜狐号和知乎 |
| `articleBody` | 文章正文，也兼容 `body` |
| `thumbnail`、`coverImages` | 封面相关路径，具体平台处理不同 |
| `dryRun` | 仅预览，不点击发布；不等于完整发布验证 |
| `isDraft` | 草稿选项，支持范围以平台实现为准 |
| `enableTimer` | 是否启用定时发布 |
| `videosPerDay`、`dailyTimes`、`startDays` | Web 批次定时配置 |

定时规则由 `utils/files_times.py` 生成：`startDays=0` 从明天开始，`startDays=1` 从后天开始；`dailyTimes` 支持整数小时或 `HH:MM`，数量不得少于 `videosPerDay`。这与 CLI 的单条 `--schedule` 参数不同。

`/postVideo` 的 `data.jobId` 用于后续轮询。`code: 200` 只表示任务已提交，最终结果应读取任务状态。其他平台专属参数与校验以 `sau_backend.py` 为准。

## 本地数据

`db/database.db` 保存账号、素材、统计和任务元数据；`cookiesFile/` 保存 Web 登录凭证，`videoFile/` 保存素材，`logs/` 保存运行日志。初始化命令为 `uv run --no-sync python db/createTable.py`，可重复执行并保留记录。
