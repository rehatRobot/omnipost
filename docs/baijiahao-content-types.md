# 百家号内容类型说明

项目代码提供百家号**视频**和**图文文章**的 Web / examples 实现，暂无统一 CLI 入口。本文描述代码处理方式；真实账号和平台页面限制尚未实测，见 [项目状态](./status.md)。

## 内容类型对比

下表记录当前实现采用的处理方式和预期页面，不作为平台现行规则的实测结论。

| 特性 | 视频 (Video) | 图文文章 (Article) |
|------|-------------|-------------------|
| 主要内容 | 视频文件 (.mp4) | 文字 + 图片 |
| 标题要求 | 1-30 字符 | 8-30 字符 |
| 封面 | 自动生成 | 可选上传 |
| 正文编辑器 | 无 | 富文本编辑器 |
| 标签支持 | ✅ | ✅ |
| 定时发布 | ✅ | ✅ |
| 发布页面 | `/builder/rc/edit?type=videoV2` | `?type=news` / `?type=article` / `?type=newsManuscript` 依次尝试（未在真实账号上验证） |

## 使用方法

### 1. 视频发布

#### 通过前端界面
1. 登录百家号账号（账号管理）
2. 上传视频文件（素材管理）
3. 选择"百家号"平台
4. 填写标题、标签
5. 点击发布

#### 通过示例脚本
```bash
uv run --no-sync python examples/upload_video_to_baijiahao.py
```

#### 通过 API
```python
POST /postVideo
{
    "type": 5,  // 百家号
    "contentType": "video",  // 视频类型
    "title": "视频标题",
    "files": ["video.mp4"],
    "tags": ["标签1", "标签2"],
    "accounts": ["account.json"],
    "enableTimer": false,
    "dryRun": false
}
```

### 2. 图文文章发布

#### 通过前端界面
1. 登录百家号账号（账号管理）
2. 选择"百家号"平台
3. **选择内容类型为"图文"** ⭐
4. 填写标题、正文、标签
5. 可选：上传封面图片
6. 点击发布

#### 通过示例脚本
```bash
uv run --no-sync python examples/upload_article_to_baijiahao.py
```

#### 通过 API
```python
POST /postVideo
{
    "type": 5,  // 百家号
    "contentType": "article",  // 图文类型 ⭐
    "title": "文章标题（至少8个字）",
    "articleBody": "这里是文章正文内容...",
    "tags": ["标签1", "标签2"],
    "accounts": ["account.json"],
    "cover": "cover.jpg",  // 可选封面
    "enableTimer": false,
    "dryRun": false
}
```

## 代码实现

### 类结构

```
uploader/baijiahao_uploader/
├── main.py
│   ├── BaiJiaHaoVideo      # 视频发布类
│   └── BaiJiaHaoArticle    # 图文文章发布类 (新增)
└── __init__.py
```

### 后端路由处理

```python
# sau_backend.py
case 5:  # 百家号
    if content_type == 'article':
        # 发布图文文章
        post_article_baijiahao(...)
    else:
        # 发布视频
        post_video_baijiahao(...)
```

## 注意事项

### 图文文章
- ✅ 标题至少 8 个字符（如果不足会自动补充）
- ✅ 正文至少 20 个字符
- ✅ 标签会自动添加到正文末尾（格式：#标签）
- ✅ 封面图片可选，支持 JPG/PNG，最大 20MB
- ⚠️ 定时发布时间选择可能不够精确（受平台限制）

### 视频
- ✅ 支持 MP4 格式视频
- ✅ 视频会自动上传并生成封面
- ✅ 标题 1-30 字符
- ⚠️ 上传大视频文件可能需要较长时间

## 测试模式 (Dry Run)

两种内容类型都支持 `dryRun` 模式：

```python
dry_run = True  # 仅预览不发布
```

在 dry_run 模式下：
- 🔍 会填充所有表单内容
- 📸 会自动截图保存（方便检查）
- ⏸️ 不会点击"发布"按钮
- ⏳ 浏览器保持打开 120 秒供人工检查

截图保存位置：
- 视频：`cookiesFile/dry_run_preview.png`
- 图文：`cookiesFile/baijiahao_article_dry_run_preview.png`

## 常见问题

### Q1: 图文文章标题太短怎么办？
A: 系统会自动补充后缀，确保至少 8 个字符。建议手动编写 8-30 字的标题。

### Q2: 如何添加文章封面？
A: 在调用 API 或脚本时，传入 `cover_path` 参数：
```python
cover_path = "videoFile/my-cover.jpg"
```

### Q3: 标签如何显示？
A: 图文文章的标签会自动添加到正文末尾，格式为 `#标签1 #标签2`

### Q4: 视频上传超时怎么办？
A: 视频上传有 10 分钟超时限制。建议：
- 压缩视频文件
- 使用更快的网络
- 检查视频格式是否正确

### Q5: Cookie 失效怎么办？
A: 运行以下命令重新获取 Cookie：
```bash
uv run --no-sync python examples/get_baijiahao_cookie.py
```

## 相关文档

- [百家号视频上传示例](../examples/upload_video_to_baijiahao.py)
- [百家号图文文章示例](../examples/upload_article_to_baijiahao.py)
- [百家号 Cookie 获取](../examples/get_baijiahao_cookie.py)
- [Web 平台入口覆盖](./legacy-web.md)

## 验证状态

本节保留该功能开发时的检查记录；当前统一验证结果见 [项目状态](./status.md)。

已验证：
- Python 侧编译与导入通过
- 两处后端调用的实参顺序与 `post_article_baijiahao` 形参一致
- 前端 `npm run build` 通过

未验证（需真实百家号账号跑一次 dryRun）：
- 图文发布页 URL 与页面选择器（标题框、正文编辑器、封面上传、发布按钮）
- 定时发布的日期/时间选择控件

首次使用请务必勾选「仅预览不发布」，据浏览器实际页面调整选择器。

## 更新日志

**2026-07-29**
- ✨ 新增 `BaiJiaHaoArticle` 类，支持图文文章发布
- ✨ 新增 `post_article_baijiahao` 函数
- ✨ 后端 `/postVideo` 与 `/postVideoBatch` 均支持 `contentType` 区分视频和图文
- ✨ 前端发布中心：百家号新增「内容类型」选择，复用正文/封面表单
- 🐛 修复后端校验只放行头条图文、导致百家号图文被「文件列表不能为空」拦截的问题
- 📝 添加示例脚本 `upload_article_to_baijiahao.py`
- 🐛 视频上传页元素定位增加多选择器回退
