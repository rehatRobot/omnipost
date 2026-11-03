import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from flask_cors import CORS
from myUtils.auth import check_cookie
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
from conf import BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen, baijiahao_cookie_gen, bilibili_cookie_gen, toutiao_cookie_gen, sohu_cookie_gen, zhihu_cookie_gen
from myUtils.creator_center import (
    PLATFORM_LABELS as CREATOR_PLATFORM_LABELS,
    cookie_path,
    get_creator_url,
    load_account,
    open_creator_center_in_thread,
)
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs, post_video_baijiahao, post_video_bilibili, post_video_toutiao, post_article_toutiao, post_article_baijiahao, post_article_sohu, post_article_zhihu
from myUtils.publish_job import (
    build_article_job_items,
    build_video_job_items,
    create_publish_job,
    finalize_publish_job,
    get_publish_job,
)
from uploader.douyin_uploader.content_stats import (
    DouyinStatsSyncError,
    ensure_content_stats_table,
    replace_account_stats,
    row_to_stat_item,
    sync_recent_items_sync as sync_douyin_content_stats,
)
from uploader.ks_uploader.content_stats import (
    KuaishouStatsSyncError,
    sync_recent_items_sync as sync_kuaishou_content_stats,
)
from uploader.xiaohongshu_uploader.content_stats import (
    XiaohongshuStatsSyncError,
    sync_recent_items_sync as sync_xiaohongshu_content_stats,
)
from uploader.bilibili_uploader.content_stats import (
    BilibiliStatsSyncError,
    sync_recent_items_sync as sync_bilibili_content_stats,
)
from uploader.tencent_uploader.content_stats import (
    TencentStatsSyncError,
    sync_recent_items_sync as sync_tencent_content_stats,
)

SUPPORTED_STATS_PLATFORMS = {
    "douyin": {"type": 3, "label": "抖音"},
    "kuaishou": {"type": 4, "label": "快手"},
    "xiaohongshu": {"type": 1, "label": "小红书"},
    "bilibili": {"type": 6, "label": "B站"},
    "tencent": {"type": 2, "label": "视频号"},
}


def _stats_platform_hint() -> str:
    return "|".join(SUPPORTED_STATS_PLATFORMS)

import conf as app_conf
from myUtils.dingtalk import (
    DingTalkPushError,
    format_multi_account_stats_markdown,
    send_markdown,
)


def _dingtalk_webhook_url() -> str:
    return (getattr(app_conf, "DINGTALK_WEBHOOK_URL", None) or "").strip()


def _dingtalk_secret() -> str:
    return (getattr(app_conf, "DINGTALK_SECRET", None) or "").strip()


def _dingtalk_rehost_covers() -> bool:
    return bool(getattr(app_conf, "DINGTALK_REHOST_COVERS", True))


def _dingtalk_push_covers() -> bool:
    return bool(getattr(app_conf, "DINGTALK_PUSH_COVERS", True))


active_queues = {}
app = Flask(__name__)


def _db_path():
    return Path(BASE_DIR / "db" / "database.db")


def _row_to_stat_item(row):
    return row_to_stat_item(row)


def _load_stats_payload(conn, platform: str, account_id: int):
    ensure_content_stats_table(conn)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM content_stats
        WHERE platform = ? AND account_id = ?
        ORDER BY published_at DESC, id DESC
        """,
        (platform, account_id),
    )
    rows = cur.fetchall()
    last = rows[0]["synced_at"] if rows else None
    return {"items": [_row_to_stat_item(r) for r in rows], "lastSyncedAt": last}

# 仅允许本机前端跨域访问（开发、预览及自定义本地端口）。
CORS(app, origins=[r"^https?://(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?$"])

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))

# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)

# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

@app.route('/vite.svg')
def vite_svg():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

# （未来打包用）
@app.route('/')
def index():  # put application's code here
    return send_from_directory(current_dir, 'index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400
    try:
        # 保存文件到指定位置
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{file.filename}")
        file.save(filepath)
        return jsonify({"code":200,"msg": "File uploaded successfully", "data": f"{uuid_v1}_{file.filename}"}), 200
    except Exception as e:
        return jsonify({"code":500,"msg": str(e),"data":None}), 500

@app.route('/getFile', methods=['GET'])
def get_file():
    # 获取 filename 参数
    filename = request.args.get('filename')

    if not filename:
        return jsonify({"code": 400, "msg": "filename is required", "data": None}), 400

    # 防止路径穿越攻击
    if '..' in filename or filename.startswith('/'):
        return jsonify({"code": 400, "msg": "Invalid filename", "data": None}), 400

    # 拼接完整路径
    file_path = str(Path(BASE_DIR / "videoFile"))

    # 返回文件
    return send_from_directory(file_path,filename)


@app.route('/uploadSave', methods=['POST'])
def upload_save():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400

    # 获取表单中的自定义文件名（可选）
    custom_filename = request.form.get('filename', None)
    if custom_filename:
        filename = custom_filename + "." + file.filename.split('.')[-1]
    else:
        filename = file.filename

    try:
        # 生成 UUID v1
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")

        # 构造文件名和路径
        final_filename = f"{uuid_v1}_{filename}"
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{filename}")

        # 保存文件
        file.save(filepath)

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                INSERT INTO file_records (filename, filesize, file_path)
            VALUES (?, ?, ?)
                                ''', (filename, round(float(os.path.getsize(filepath)) / (1024 * 1024),2), final_filename))
            conn.commit()
            print("✅ 上传文件已记录")

        return jsonify({
            "code": 200,
            "msg": "File uploaded and saved successfully",
            "data": {
                "filename": filename,
                "filepath": final_filename
            }
        }), 200

    except Exception as e:
        print(f"Upload failed: {e}")
        return jsonify({
            "code": 500,
            "msg": f"upload failed: {e}",
            "data": None
        }), 500

def format_sqlite_utc_to_local(value):
    """SQLite CURRENT_TIMESTAMP 存的是 UTC，转成系统本地时间再展示。"""
    if not value:
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return value


@app.route('/getFiles', methods=['GET'])
def get_all_files():
    try:
        # 使用 with 自动管理数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row  # 允许通过列名访问结果
            cursor = conn.cursor()

            # 查询所有记录
            cursor.execute("SELECT * FROM file_records")
            rows = cursor.fetchall()
            
            # 将结果转为字典列表，并提取UUID
            data = []
            for row in rows:
                row_dict = dict(row)
                row_dict['upload_time'] = format_sqlite_utc_to_local(row_dict.get('upload_time'))
                # 从 file_path 中提取 UUID (文件名的第一部分，下划线前)
                if row_dict.get('file_path'):
                    file_path_parts = row_dict['file_path'].split('_', 1)  # 只分割第一个下划线
                    if len(file_path_parts) > 0:
                        row_dict['uuid'] = file_path_parts[0]  # UUID 部分
                    else:
                        row_dict['uuid'] = ''
                else:
                    row_dict['uuid'] = ''
                data.append(row_dict)

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": data
            }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("get file failed!"),
            "data": None
        }), 500


@app.route("/getAccounts", methods=['GET'])
def getAccounts():
    """快速获取所有账号信息，不进行cookie验证"""
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM user_info''')
            rows = cursor.fetchall()
            rows_list = [list(row) for row in rows]

            print("\n📋 当前数据表内容（快速获取）：")
            for row in rows:
                print(row)

            return jsonify(
                {
                    "code": 200,
                    "msg": None,
                    "data": rows_list
                }), 200
    except Exception as e:
        print(f"获取账号列表时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"获取账号列表失败: {str(e)}",
            "data": None
        }), 500


@app.route("/getValidAccounts",methods=['GET'])
async def getValidAccounts():
    platform_type = request.args.get('type')
    if platform_type is not None:
        try:
            platform_type = int(platform_type)
        except ValueError:
            return jsonify({
                "code": 400,
                "msg": "Invalid platform type",
                "data": None
            }), 400

    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        if platform_type is not None:
            cursor.execute('SELECT * FROM user_info WHERE type = ?', (platform_type,))
        else:
            cursor.execute('SELECT * FROM user_info')
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        scope = f"type={platform_type}" if platform_type is not None else "all"
        print(f"\n📋 校验账号 ({scope})，共 {len(rows_list)} 条：")
        for row in rows:
            print(row)
        for row in rows_list:
            flag = await check_cookie(row[1],row[2])
            new_status = 1 if flag else 0
            row[4] = new_status
            cursor.execute('''
            UPDATE user_info 
            SET status = ? 
            WHERE id = ?
            ''', (new_status, row[0]))
            conn.commit()
            print(f"✅ 用户状态已更新 id={row[0]} status={new_status}")
        return jsonify(
                        {
                            "code": 200,
                            "msg": None,
                            "data": rows_list
                        }),200


@app.route("/openCreatorCenter", methods=["POST"])
def open_creator_center():
    """用已保存 cookie 打开对应平台创作者中心（有头浏览器）。"""
    data = request.get_json(silent=True) or {}
    account_id = data.get("id") if data else request.args.get("id")
    if account_id is None:
        return jsonify({"code": 400, "msg": "缺少账号 id", "data": None}), 400
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "账号 id 无效", "data": None}), 400

    try:
        account = load_account(account_id)
        url = get_creator_url(account["type"])
        if not url:
            return jsonify({
                "code": 400,
                "msg": f"不支持的平台类型: {account['type']}",
                "data": None,
            }), 400
        cookie_path(account["filePath"])
    except FileNotFoundError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None}), 404
    except ValueError as e:
        return jsonify({"code": 404, "msg": str(e), "data": None}), 404
    except Exception as e:
        return jsonify({"code": 500, "msg": f"校验失败: {e}", "data": None}), 500

    thread = threading.Thread(
        target=open_creator_center_in_thread,
        args=(account_id,),
        daemon=True,
    )
    thread.start()

    label = CREATOR_PLATFORM_LABELS.get(account["type"], "未知平台")
    return jsonify({
        "code": 200,
        "msg": f"正在打开 {label} 创作者中心",
        "data": {
            "accountId": account_id,
            "platform": label,
            "userName": account["userName"],
            "url": url,
        },
    }), 200


@app.route('/deleteFile', methods=['GET'])
def delete_file():
    file_id = request.args.get('id')

    if not file_id or not file_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing file ID",
            "data": None
        }), 400

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "File not found",
                    "data": None
                }), 404

            record = dict(record)

            # 获取文件路径并删除实际文件
            file_path = Path(BASE_DIR / "videoFile" / record['file_path'])
            if file_path.exists():
                try:
                    file_path.unlink()  # 删除文件
                    print(f"✅ 实际文件已删除: {file_path}")
                except Exception as e:
                    print(f"⚠️ 删除实际文件失败: {e}")
                    # 即使删除文件失败，也要继续删除数据库记录，避免数据不一致
            else:
                print(f"⚠️ 实际文件不存在: {file_path}")

            # 删除数据库记录
            cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "File deleted successfully",
            "data": {
                "id": record['id'],
                "filename": record['filename']
            }
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("delete failed!"),
            "data": None
        }), 500

@app.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = request.args.get('id')

    if not account_id or not account_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing account ID",
            "data": None
        }), 400

    account_id = int(account_id)

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            record = dict(record)

            # 删除关联的cookie文件
            if record.get('filePath'):
                cookie_file_path = Path(BASE_DIR / "cookiesFile" / record['filePath'])
                if cookie_file_path.exists():
                    try:
                        cookie_file_path.unlink()
                        print(f"✅ Cookie文件已删除: {cookie_file_path}")
                    except Exception as e:
                        print(f"⚠️ 删除Cookie文件失败: {e}")

            # 删除数据库记录
            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account deleted successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"delete failed: {str(e)}",
            "data": None
        }), 500


# SSE 登录接口
@app.route('/login')
def login():
    # 1 小红书 2 视频号 3 抖音 4 快手 5 百家号 6 B站 7 今日头条
    type = request.args.get('type')
    # 账号名
    id = request.args.get('id')
    print(f"登录请求: type={type}, id={id}")

    # 模拟一个用于异步通信的队列
    status_queue = Queue()
    active_queues[id] = status_queue

    def on_close():
        print(f"清理队列: {id}")
        del active_queues[id]
    # 启动异步任务线程
    thread = threading.Thread(target=run_async_function, args=(type,id,status_queue), daemon=True)
    thread.start()
    response = Response(sse_stream(status_queue,), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/postVideo', methods=['POST'])
def postVideo():
    # 获取JSON数据
    data = request.get_json()

    if not data:
        return jsonify({"code": 400, "msg": "请求数据不能为空", "data": None}), 400

    # 从JSON数据中提取fileList和accountList
    file_list = data.get('fileList', [])
    account_list = data.get('accountList', [])
    type = data.get('type')
    title = data.get('title')
    tags = data.get('tags')
    category = data.get('category')
    enableTimer = data.get('enableTimer')
    if category == 0:
        category = None
    productLink = data.get('productLink', '')
    productTitle = data.get('productTitle', '')
    thumbnail_path = data.get('thumbnail', '') or data.get('coverImage', '')
    cover_images = data.get('coverImages') or data.get('cover_images') or []
    if isinstance(cover_images, str):
        cover_images = [x.strip() for x in cover_images.split(',') if x.strip()]
    elif not isinstance(cover_images, list):
        cover_images = []
    else:
        cover_images = [str(x).strip() for x in cover_images if str(x).strip()]
    # 兼容：仅传单图时并入 coverImages
    if thumbnail_path and str(thumbnail_path).strip() and str(thumbnail_path).strip() not in cover_images:
        if not cover_images:
            cover_images = [str(thumbnail_path).strip()]
    is_draft = data.get('isDraft', False)  # 新增参数：是否保存为草稿
    ai_generated = data.get('aiGenerated', False)  # 抖音/快手/小红书/视频号 AI 内容声明
    dry_run = data.get('dryRun', False)  # 仅预览不发布：填完表后不点发布
    # B站创作声明 id：-1/1/2/3/4；None 表示不传
    bilibili_creation_statement = data.get('bilibiliCreationStatement', None)
    # 今日头条内容类型：video（默认）| article
    content_type = (data.get('contentType') or 'video').strip().lower()
    article_body = data.get('articleBody') or data.get('body') or ''
    # 今日头条图文作品声明（单选）
    work_statement = data.get('workStatement') or data.get('work_statement') or ''
    work_statements = data.get('workStatements') or data.get('work_statements') or []
    if work_statement and str(work_statement).strip():
        work_statements = [str(work_statement).strip()]
    elif isinstance(work_statements, str):
        work_statements = [work_statements] if work_statements.strip() else []
    elif not isinstance(work_statements, list):
        work_statements = []
    else:
        work_statements = [str(x).strip() for x in work_statements if str(x).strip()]
    # 单选：最多保留第一项
    work_statements = work_statements[:1]

    videos_per_day = data.get('videosPerDay')
    daily_times = data.get('dailyTimes')
    start_days = data.get('startDays')

    if type is None or type == "":
        return jsonify({"code": 400, "msg": "平台类型不能为空", "data": None}), 400
    try:
        type = int(type)
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": f"不支持的平台类型: {type}", "data": None}), 400

    # 支持图文文章的平台：5=百家号，7=今日头条，8=搜狐号，9=知乎
    ARTICLE_CAPABLE_PLATFORMS = (5, 7, 8, 9)
    # 搜狐号/知乎第一期仅支持图文
    if type == 8:
        content_type = 'article'
    if type == 9:
        content_type = 'article'
    is_article = (type in ARTICLE_CAPABLE_PLATFORMS and content_type == 'article')
    is_toutiao_article = (type == 7 and content_type == 'article')
    is_baijiahao_article = (type == 5 and content_type == 'article')
    is_sohu_article = (type == 8)
    is_zhihu_article = (type == 9)

    # 参数校验
    if not is_article and not file_list:
        return jsonify({"code": 400, "msg": "文件列表不能为空", "data": None}), 400
    if not account_list:
        return jsonify({"code": 400, "msg": "账号列表不能为空", "data": None}), 400
    if is_article:
        if not title or not str(title).strip():
            return jsonify({"code": 400, "msg": "文章标题不能为空", "data": None}), 400
        if is_sohu_article:
            title_len = len(str(title).strip())
            if title_len < 5 or title_len > 72:
                return jsonify({"code": 400, "msg": "搜狐号文章标题需 5-72 个字", "data": None}), 400
        if is_zhihu_article:
            title_len = len(str(title).strip())
            if title_len > 100:
                return jsonify({"code": 400, "msg": "知乎文章标题最多 100 个字", "data": None}), 400
        if not article_body or not str(article_body).strip():
            return jsonify({"code": 400, "msg": "文章正文不能为空", "data": None}), 400
        # 百家号图文标题下限 2 字
        if is_baijiahao_article and len(str(title).strip()) < 2:
            return jsonify({"code": 400, "msg": "百家号图文标题至少 2 个字", "data": None}), 400
        if is_baijiahao_article and not str(thumbnail_path or "").strip():
            return jsonify({"code": 400, "msg": "百家号图文展示封面不能为空", "data": None}), 400
    # 小红书（1）、视频号（2）、抖音（3）、快手（4）标题非必填，其它平台仍必填
    elif type not in (1, 2, 3, 4) and not title:
        return jsonify({"code": 400, "msg": "标题不能为空", "data": None}), 400
    if title is None:
        title = ""
    if is_sohu_article:
        title = str(title).strip()[:72]
    if is_zhihu_article:
        title = str(title).strip()[:100]
    if bilibili_creation_statement is not None and bilibili_creation_statement != "":
        try:
            bilibili_creation_statement = int(bilibili_creation_statement)
        except (TypeError, ValueError):
            return jsonify({"code": 400, "msg": f"非法的创作声明: {bilibili_creation_statement}", "data": None}), 400
    else:
        bilibili_creation_statement = None

    # 打印获取到的数据（仅作为示例）
    print("File List:", file_list)
    print("Account List:", account_list)
    print(
        f"enableTimer={enableTimer}, dryRun={dry_run}, aiGenerated={ai_generated}, "
        f"bilibiliCreationStatement={bilibili_creation_statement}, "
        f"contentType={content_type}, cover={thumbnail_path}, workStatements={work_statements}",
        flush=True,
    )

    # 参数校验通过后，在后台线程中执行发布任务，避免阻塞Flask主线程。
    # 前端拿到的 200 只表示“任务已提交”，真实结果通过 jobId 轮询 /publishJob/<id>。
    if is_article:
        job_items = build_article_job_items(title, account_list)
    else:
        job_items = build_video_job_items(file_list, account_list)
    job_id = create_publish_job(type, title, job_items)

    def run_publish_task():
        try:
            print(
                f"🧵 后台发布线程启动: jobId={job_id}, type={type}, title={title}, dryRun={dry_run}, contentType={content_type}",
                flush=True,
            )
            match type:
                case 1:
                    post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                       start_days, dry_run, ai_generated, job_id)
                case 2:
                    post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                       start_days, is_draft, dry_run, ai_generated, job_id)
                case 3:
                    post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                              start_days, thumbnail_path, productLink, productTitle, ai_generated, dry_run, job_id)
                case 4:
                    post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                              start_days, dry_run, ai_generated, job_id)
                case 5:
                    if content_type == 'article':
                        post_article_baijiahao(
                            title,
                            article_body,
                            tags,
                            account_list,
                            enableTimer,
                            videos_per_day,
                            daily_times,
                            start_days,
                            dry_run,
                            thumbnail_path,
                            ai_generated,
                            job_id,
                        )
                    else:
                        post_video_baijiahao(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                  start_days, dry_run, job_id)
                case 6:
                    post_video_bilibili(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                              start_days, dry_run, bilibili_creation_statement, job_id)
                case 7:
                    if content_type == 'article':
                        post_article_toutiao(
                            title,
                            article_body,
                            tags,
                            account_list,
                            enableTimer,
                            videos_per_day,
                            daily_times,
                            start_days,
                            dry_run,
                            thumbnail_path,
                            work_statements,
                            job_id,
                        )
                    else:
                        post_video_toutiao(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                  start_days, dry_run, job_id)
                case 8:
                    post_article_sohu(
                        title,
                        article_body,
                        tags,
                        account_list,
                        enableTimer,
                        videos_per_day,
                        daily_times,
                        start_days,
                        dry_run,
                        thumbnail_path,
                        work_statements[0] if work_statements else (work_statement or None),
                        cover_images,
                        job_id,
                    )
                case 9:
                    post_article_zhihu(
                        title,
                        article_body,
                        tags,
                        account_list,
                        enableTimer,
                        videos_per_day,
                        daily_times,
                        start_days,
                        dry_run,
                        thumbnail_path,
                        work_statements[0] if work_statements else (work_statement or None),
                        job_id,
                    )
            print(f"✅ 发布任务完成: jobId={job_id}, type={type}, title={title}", flush=True)
        except Exception as e:
            print(f"❌ 发布视频时出错: jobId={job_id}, {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            try:
                finalize_publish_job(job_id)
            except Exception as finalize_err:
                print(f"❌ 汇总发布任务失败: jobId={job_id}, {finalize_err}", flush=True)

    thread = threading.Thread(target=run_publish_task, daemon=True)
    thread.start()

    if type == 6 and dry_run:
        submit_msg = "B站仅预览模式不会实际上传（无浏览器可预览）"
    elif type == 6:
        submit_msg = "B站上传任务已提交，后台通过 biliup 执行（不会打开浏览器）"
    elif is_toutiao_article and dry_run:
        submit_msg = "今日头条文章任务已提交：仅预览不发布"
    elif is_toutiao_article:
        submit_msg = "今日头条文章发布任务已提交，正在后台执行"
    elif is_sohu_article and dry_run:
        submit_msg = "搜狐号文章任务已提交：仅预览不发布"
    elif is_sohu_article:
        submit_msg = "搜狐号文章发布任务已提交，正在后台执行"
    elif is_zhihu_article and dry_run:
        submit_msg = "知乎文章任务已提交：仅预览不发布"
    elif is_zhihu_article:
        submit_msg = "知乎文章发布任务已提交，正在后台执行"
    elif type == 5 and content_type == 'article' and dry_run:
        submit_msg = "百家号图文文章任务已提交：仅预览不发布（可能出现自动保存草稿，不等于已发布）"
    elif type == 5 and content_type == 'article':
        submit_msg = "百家号图文文章发布任务已提交，浏览器将自动打开"
    elif type == 5:
        submit_msg = "百家号视频发布任务已提交，浏览器将自动打开上传"
    else:
        submit_msg = "发布任务已提交，正在后台执行"

    return jsonify(
        {
            "code": 200,
            "msg": submit_msg,
            "data": {"jobId": job_id}
        }), 200


@app.route('/publishJob/<int:job_id>', methods=['GET'])
def publish_job_status(job_id: int):
    job = get_publish_job(job_id)
    if not job:
        return jsonify({"code": 404, "msg": "发布任务不存在", "data": None}), 404
    return jsonify({"code": 200, "msg": "ok", "data": job}), 200


@app.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    # 获取JSON数据
    data = request.get_json()

    # 从JSON数据中提取 type 和 userName
    user_id = data.get('id')
    type = data.get('type')
    userName = data.get('userName')
    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 更新数据库记录
            cursor.execute('''
                           UPDATE user_info
                           SET type     = ?,
                               userName = ?
                           WHERE id = ?;
                           ''', (type, userName, user_id))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account update successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("update failed!"),
            "data": None
        }), 500

@app.route('/postVideoBatch', methods=['POST'])
def postVideoBatch():
    data_list = request.get_json()

    if not isinstance(data_list, list):
        return jsonify({"code": 400, "msg": "Expected a JSON array", "data": None}), 400
    for data in data_list:
        # 从JSON数据中提取fileList和accountList
        file_list = data.get('fileList', [])
        account_list = data.get('accountList', [])
        type = data.get('type')
        title = data.get('title')
        tags = data.get('tags')
        category = data.get('category')
        enableTimer = data.get('enableTimer')
        if category == 0:
            category = None
        productLink = data.get('productLink', '')
        productTitle = data.get('productTitle', '')
        is_draft = data.get('isDraft', False)
        ai_generated = data.get('aiGenerated', False)
        dry_run = data.get('dryRun', False)
        thumbnail_path = data.get('thumbnail', '') or data.get('coverImage', '')
        cover_images = data.get('coverImages') or data.get('cover_images') or []
        if isinstance(cover_images, str):
            cover_images = [x.strip() for x in cover_images.split(',') if x.strip()]
        elif not isinstance(cover_images, list):
            cover_images = []
        else:
            cover_images = [str(x).strip() for x in cover_images if str(x).strip()]
        if thumbnail_path and str(thumbnail_path).strip() and str(thumbnail_path).strip() not in cover_images:
            if not cover_images:
                cover_images = [str(thumbnail_path).strip()]
        content_type = (data.get('contentType') or 'video').strip().lower()
        article_body = data.get('articleBody') or data.get('body') or ''
        work_statement = data.get('workStatement') or data.get('work_statement') or ''
        work_statements = data.get('workStatements') or data.get('work_statements') or []
        if work_statement and str(work_statement).strip():
            work_statements = [str(work_statement).strip()]
        elif isinstance(work_statements, str):
            work_statements = [work_statements] if work_statements.strip() else []
        elif not isinstance(work_statements, list):
            work_statements = []
        else:
            work_statements = [str(x).strip() for x in work_statements if str(x).strip()]
        work_statements = work_statements[:1]
        bilibili_creation_statement = data.get('bilibiliCreationStatement', None)
        if bilibili_creation_statement is not None and bilibili_creation_statement != "":
            try:
                bilibili_creation_statement = int(bilibili_creation_statement)
            except (TypeError, ValueError):
                bilibili_creation_statement = None
        else:
            bilibili_creation_statement = None

        videos_per_day = data.get('videosPerDay')
        daily_times = data.get('dailyTimes')
        start_days = data.get('startDays')
        # 搜狐号/知乎第一期仅支持图文
        if type == 8:
            content_type = 'article'
            title_text = str(title or "").strip()
            if len(title_text) < 5 or len(title_text) > 72:
                return jsonify({"code": 400, "msg": "搜狐号文章标题需 5-72 个字", "data": None}), 400
            title = title_text[:72]
        if type == 9:
            content_type = 'article'
            title_text = str(title or "").strip()
            if len(title_text) > 100:
                return jsonify({"code": 400, "msg": "知乎文章标题最多 100 个字", "data": None}), 400
            title = title_text[:100]
        is_baijiahao_article = (type == 5 and content_type == 'article')
        if is_baijiahao_article and not str(thumbnail_path or "").strip():
            return jsonify({"code": 400, "msg": "百家号图文展示封面不能为空", "data": None}), 400
        # 打印获取到的数据（仅作为示例）
        print("File List:", file_list)
        print("Account List:", account_list)
        match type:
            case 1:
                post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                               start_days, dry_run, ai_generated)
            case 2:
                post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days, is_draft, dry_run, ai_generated)
            case 3:
                post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days, thumbnail_path, productLink, productTitle, ai_generated, dry_run)
            case 4:
                post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days, dry_run)
            case 5:
                if content_type == 'article':
                    post_article_baijiahao(
                        title,
                        article_body,
                        tags,
                        account_list,
                        enableTimer,
                        videos_per_day,
                        daily_times,
                        start_days,
                        dry_run,
                        thumbnail_path,
                    )
                else:
                    post_video_baijiahao(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                              start_days, dry_run)
            case 6:
                post_video_bilibili(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days, dry_run, bilibili_creation_statement)
            case 7:
                if content_type == 'article':
                    post_article_toutiao(
                        title,
                        article_body,
                        tags,
                        account_list,
                        enableTimer,
                        videos_per_day,
                        daily_times,
                        start_days,
                        dry_run,
                        thumbnail_path,
                        work_statements,
                    )
                else:
                    post_video_toutiao(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                              start_days, dry_run)
            case 8:
                post_article_sohu(
                    title,
                    article_body,
                    tags,
                    account_list,
                    enableTimer,
                    videos_per_day,
                    daily_times,
                    start_days,
                    dry_run,
                    thumbnail_path,
                    work_statements[0] if work_statements else (work_statement or None),
                    cover_images,
                )
            case 9:
                post_article_zhihu(
                    title,
                    article_body,
                    tags,
                    account_list,
                    enableTimer,
                    videos_per_day,
                    daily_times,
                    start_days,
                    dry_run,
                    thumbnail_path,
                    work_statements[0] if work_statements else (work_statement or None),
                )
    # 返回响应给客户端
    return jsonify(
        {
            "code": 200,
            "msg": None,
            "data": None
        }), 200

# Cookie文件上传API
@app.route('/uploadCookie', methods=['POST'])
def upload_cookie():
    try:
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "msg": "没有找到Cookie文件",
                "data": None
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "msg": "Cookie文件名不能为空",
                "data": None
            }), 400

        if not file.filename.endswith('.json'):
            return jsonify({
                "code": 400,
                "msg": "Cookie文件必须是JSON格式",
                "data": None
            }), 400

        # 获取账号信息
        account_id = request.form.get('id')
        platform = request.form.get('platform')

        if not account_id or not platform:
            return jsonify({
                "code": 400,
                "msg": "缺少账号ID或平台信息",
                "data": None
            }), 400

        # 从数据库获取账号的文件路径
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT filePath FROM user_info WHERE id = ?', (account_id,))
            result = cursor.fetchone()

        if not result:
            return jsonify({
                "code": 500,
                "msg": "账号不存在",
                "data": None
            }), 404

        # 保存上传的Cookie文件到对应路径
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / result['filePath'])
        cookie_file_path.parent.mkdir(parents=True, exist_ok=True)

        file.save(str(cookie_file_path))

        # 更新数据库中的账号信息（可选，比如更新更新时间）
        # 这里可以根据需要添加额外的处理逻辑

        return jsonify({
            "code": 200,
            "msg": "Cookie文件上传成功",
            "data": None
        }), 200

    except Exception as e:
        print(f"上传Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"上传Cookie文件失败: {str(e)}",
            "data": None
        }), 500


# Cookie文件下载API
@app.route('/downloadCookie', methods=['GET'])
def download_cookie():
    try:
        file_path = request.args.get('filePath')
        if not file_path:
            return jsonify({
                "code": 500,
                "msg": "缺少文件路径参数",
                "data": None
            }), 400

        # 验证文件路径的安全性，防止路径遍历攻击
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / file_path).resolve()
        base_path = Path(BASE_DIR / "cookiesFile").resolve()

        if not cookie_file_path.is_relative_to(base_path):
            return jsonify({
                "code": 500,
                "msg": "非法文件路径",
                "data": None
            }), 400

        if not cookie_file_path.exists():
            return jsonify({
                "code": 500,
                "msg": "Cookie文件不存在",
                "data": None
            }), 404

        # 返回文件
        return send_from_directory(
            directory=str(cookie_file_path.parent),
            path=cookie_file_path.name,
            as_attachment=True
        )

    except Exception as e:
        print(f"下载Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"下载Cookie文件失败: {str(e)}",
            "data": None
        }), 500


@app.route("/proxyImage", methods=["GET"])
def proxy_image():
    """代理外链封面图，规避 B 站等 CDN 防盗链。"""
    from urllib.parse import urlparse

    import requests as http_requests

    raw_url = (request.args.get("url") or "").strip()
    if not raw_url:
        return jsonify({"code": 400, "msg": "url 不能为空", "data": None}), 400
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return jsonify({"code": 400, "msg": "url 无效", "data": None}), 400
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify({"code": 400, "msg": "仅支持 http/https 图片地址", "data": None}), 400
    host = parsed.hostname
    if not host:
        return jsonify({"code": 400, "msg": "url 无效", "data": None}), 400
    host = host.lower()
    allowed_suffixes = (".hdslb.com",)
    allowed_exact = {"hdslb.com"}
    if not (host in allowed_exact or any(host.endswith(suf) for suf in allowed_suffixes)):
        return jsonify({"code": 403, "msg": "该图片域名不允许代理", "data": None}), 403

    try:
        upstream = http_requests.get(
            raw_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/",
            },
            timeout=20,
            stream=True,
        )
    except Exception as e:
        return jsonify({"code": 502, "msg": f"拉取图片失败: {e}", "data": None}), 502
    if upstream.status_code != 200:
        return jsonify({"code": 502, "msg": f"上游返回 {upstream.status_code}", "data": None}), 502

    content_type = (upstream.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    if not content_type.startswith("image/"):
        return jsonify({"code": 502, "msg": "上游不是图片", "data": None}), 502

    # cap ~5MB
    chunks = []
    total = 0
    for chunk in upstream.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > 5 * 1024 * 1024:
            return jsonify({"code": 502, "msg": "图片过大", "data": None}), 502
        chunks.append(chunk)
    body = b"".join(chunks)
    return Response(body, status=200, mimetype=content_type, headers={
        "Cache-Control": "public, max-age=86400",
    })


@app.route("/getContentStats", methods=["GET"])
def get_content_stats():
    account_id = request.args.get("accountId", type=int)
    platform = (request.args.get("platform") or "douyin").strip().lower()
    if not account_id:
        return jsonify({"code": 400, "msg": "accountId 不能为空", "data": None}), 400
    if platform not in SUPPORTED_STATS_PLATFORMS:
        return jsonify({"code": 400, "msg": f"仅支持 platform={_stats_platform_hint()}", "data": None}), 400
    try:
        with sqlite3.connect(_db_path()) as conn:
            payload = _load_stats_payload(conn, platform, account_id)
        return jsonify({"code": 200, "msg": None, "data": payload}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": f"读取失败: {e}", "data": None}), 500


@app.route("/syncContentStats", methods=["POST"])
def sync_content_stats():
    body = request.get_json(silent=True) or {}
    account_id = body.get("accountId")
    platform = str(body.get("platform") or "douyin").strip().lower()
    try:
        limit = int(body.get("limit") or 5)
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "limit 无效", "data": None}), 400
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "accountId 无效", "data": None}), 400
    meta = SUPPORTED_STATS_PLATFORMS.get(platform)
    if not meta:
        return jsonify({"code": 400, "msg": f"仅支持 platform={_stats_platform_hint()}", "data": None}), 400
    if limit < 1 or limit > 20:
        return jsonify({"code": 400, "msg": "limit 需在 1-20", "data": None}), 400

    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, type, filePath FROM user_info WHERE id = ?", (account_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404
            if int(row["type"]) != meta["type"]:
                return jsonify({"code": 400, "msg": f"该账号不是{meta['label']}账号", "data": None}), 400
            cookie_path = Path(BASE_DIR / "cookiesFile" / row["filePath"])
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询账号失败: {e}", "data": None}), 500

    try:
        if platform == "douyin":
            items = sync_douyin_content_stats(cookie_path, limit=limit)
        elif platform == "kuaishou":
            items = sync_kuaishou_content_stats(cookie_path, limit=limit)
        elif platform == "xiaohongshu":
            items = sync_xiaohongshu_content_stats(cookie_path, limit=limit)
        elif platform == "tencent":
            items = sync_tencent_content_stats(cookie_path, limit=limit)
        else:
            items = sync_bilibili_content_stats(cookie_path, limit=limit)
    except (
        DouyinStatsSyncError,
        KuaishouStatsSyncError,
        XiaohongshuStatsSyncError,
        BilibiliStatsSyncError,
        TencentStatsSyncError,
    ) as e:
        return jsonify({"code": e.code, "msg": e.message, "data": None}), e.code
    except Exception as e:
        return jsonify({"code": 500, "msg": f"同步失败: {e}", "data": None}), 500

    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(_db_path()) as conn:
            replace_account_stats(
                conn,
                platform=platform,
                account_id=account_id,
                items=items,
                synced_at=synced_at,
            )
            payload = _load_stats_payload(conn, platform, account_id)
        return jsonify({"code": 200, "msg": "同步成功", "data": payload}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": f"写入失败: {e}", "data": None}), 500


@app.route("/pushContentStatsToDingTalk", methods=["POST"])
def push_content_stats_to_dingtalk():
    body = request.get_json(silent=True) or {}
    webhook = _dingtalk_webhook_url()
    if not webhook:
        return jsonify({"code": 400, "msg": "未配置 DINGTALK_WEBHOOK_URL", "data": None}), 400

    raw_accounts = body.get("accounts")
    targets = []
    if isinstance(raw_accounts, list) and raw_accounts:
        for entry in raw_accounts:
            if not isinstance(entry, dict):
                return jsonify({"code": 400, "msg": "accounts 项无效", "data": None}), 400
            platform = str(entry.get("platform") or "").strip().lower()
            try:
                account_id = int(entry.get("accountId"))
            except (TypeError, ValueError):
                return jsonify({"code": 400, "msg": "accountId 无效", "data": None}), 400
            if platform not in SUPPORTED_STATS_PLATFORMS:
                return jsonify(
                    {
                        "code": 400,
                        "msg": f"仅支持 platform={_stats_platform_hint()}",
                        "data": None,
                    }
                ), 400
            targets.append({"accountId": account_id, "platform": platform})
    else:
        platform = str(body.get("platform") or "douyin").strip().lower()
        try:
            account_id = int(body.get("accountId"))
        except (TypeError, ValueError):
            return jsonify({"code": 400, "msg": "accountId 无效", "data": None}), 400
        if platform not in SUPPORTED_STATS_PLATFORMS:
            return jsonify(
                {
                    "code": 400,
                    "msg": f"仅支持 platform={_stats_platform_hint()}",
                    "data": None,
                }
            ), 400
        targets.append({"accountId": account_id, "platform": platform})

    # de-dupe while preserving order
    seen = set()
    unique_targets = []
    for t in targets:
        key = (t["platform"], t["accountId"])
        if key in seen:
            continue
        seen.add(key)
        unique_targets.append(t)
    targets = unique_targets

    if not targets:
        return jsonify({"code": 400, "msg": "请选择账号", "data": None}), 400
    if len(targets) > 20:
        return jsonify({"code": 400, "msg": "一次最多推送 20 个账号", "data": None}), 400

    sections = []
    skipped = []
    try:
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            for t in targets:
                platform = t["platform"]
                account_id = t["accountId"]
                meta = SUPPORTED_STATS_PLATFORMS[platform]
                cur.execute(
                    "SELECT id, type, userName FROM user_info WHERE id = ?",
                    (account_id,),
                )
                row = cur.fetchone()
                if not row:
                    skipped.append({"accountId": account_id, "platform": platform, "reason": "账号不存在"})
                    continue
                if int(row["type"]) != meta["type"]:
                    skipped.append(
                        {
                            "accountId": account_id,
                            "platform": platform,
                            "reason": f"不是{meta['label']}账号",
                        }
                    )
                    continue
                payload = _load_stats_payload(conn, platform, account_id)
                items = payload.get("items") or []
                if not items:
                    skipped.append(
                        {
                            "accountId": account_id,
                            "platform": platform,
                            "accountName": row["userName"] or str(account_id),
                            "reason": "尚未同步",
                        }
                    )
                    continue
                sections.append(
                    {
                        "platform_label": meta["label"],
                        "account_name": row["userName"] or str(account_id),
                        "last_synced_at": payload.get("lastSyncedAt"),
                        "items": items,
                        "accountId": account_id,
                        "platform": platform,
                    }
                )
    except Exception as e:
        return jsonify({"code": 500, "msg": f"读取失败: {e}", "data": None}), 500

    if not sections:
        return jsonify(
            {
                "code": 400,
                "msg": "所选账号均无已同步数据，请先同步",
                "data": {"skipped": skipped},
            }
        ), 400

    try:
        title, text = format_multi_account_stats_markdown(
            sections=sections,
            rehost_covers=_dingtalk_rehost_covers(),
            include_covers=_dingtalk_push_covers(),
        )
        send_markdown(
            webhook_url=webhook,
            secret=_dingtalk_secret(),
            title=title,
            text=text,
        )
    except DingTalkPushError as e:
        return jsonify({"code": e.code, "msg": e.message, "data": None}), e.code
    except Exception as e:
        return jsonify({"code": 502, "msg": f"推送失败: {e}", "data": None}), 502

    item_count = sum(len(s["items"]) for s in sections)
    return jsonify(
        {
            "code": 200,
            "msg": "推送成功",
            "data": {
                "accountCount": len(sections),
                "itemCount": item_count,
                "skipped": skipped,
            },
        }
    ), 200


# 包装函数：在线程中运行异步函数
def run_async_function(type,id,status_queue):
    print(f"🧵 登录线程启动: type={type}, id={id}", flush=True)
    try:
        match str(type):
            case '1':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
                loop.close()
            case '2':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_tencent_cookie(id,status_queue))
                loop.close()
            case '3':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(douyin_cookie_gen(id,status_queue))
                loop.close()
            case '4':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_ks_cookie(id,status_queue))
                loop.close()
            case '5':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(baijiahao_cookie_gen(id, status_queue))
                loop.close()
            case '6':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(bilibili_cookie_gen(id, status_queue))
                loop.close()
            case '7':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(toutiao_cookie_gen(id, status_queue))
                loop.close()
            case '8':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(sohu_cookie_gen(id, status_queue))
                loop.close()
            case '9':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(zhihu_cookie_gen(id, status_queue))
                loop.close()
            case _:
                print(f"❌ 不支持的登录平台类型: {type}", flush=True)
                status_queue.put("500")
    except Exception as e:
        print(f"❌ 登录线程异常 type={type}, id={id}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        try:
            status_queue.put("500")
        except Exception:
            pass

# SSE 流生成器函数
def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            # 避免 CPU 占满
            time.sleep(0.1)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5409)
