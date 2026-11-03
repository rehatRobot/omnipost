import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.baijiahao_uploader.main import BaiJiaHaoVideo, BaiJiaHaoArticle
from uploader.bilibili_uploader.runtime import run_biliup_command
from uploader.douyin_uploader.main import (
    DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
    DOUYIN_PUBLISH_STRATEGY_SCHEDULED,
    DouYinVideo,
)
from uploader.ks_uploader.main import KSVideo
from uploader.tencent_uploader.main import (
    TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
    TENCENT_PUBLISH_STRATEGY_SCHEDULED,
    TencentVideo,
)
from uploader.toutiao_uploader.main import TouTiaoArticle, TouTiaoVideo
from uploader.sohu_uploader.main import SoHuArticle
from uploader.zhihu_uploader.main import ZhiHuArticle
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from utils.constant import TencentZoneTypes
from utils.files_times import generate_schedule_time_next_day
from myUtils.publish_job import run_tracked_upload


def post_video_tencent(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, is_draft=False, dry_run=False, ai_generated=False, job_id=None):
    # 生成文件的完整路径（保留原始相对名供任务结果回写）
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"文件路径{str(file)}")
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            print(f"仅预览不发布：{dry_run}")
            print(f"视频标注(AI)：{ai_generated}")
            kwargs = dict(
                title=title,
                file_path=str(file),
                tags=tags,
                publish_date=publish_datetimes[index],
                account_file=cookie,
                category=category,
                is_draft=is_draft,
                dry_run=dry_run,
                ai_generated=ai_generated,
                publish_strategy=(
                    TENCENT_PUBLISH_STRATEGY_SCHEDULED
                    if enableTimer
                    else TENCENT_PUBLISH_STRATEGY_IMMEDIATE
                ),
            )
            if dry_run:
                kwargs["headless"] = False

            def _do_upload(kw=kwargs):
                app = TencentVideo(**kw)
                asyncio.run(app.main(), debug=False)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)


def post_video_DouYin(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0,
                      thumbnail_path = '',
                      productLink = '', productTitle = '',
                      ai_generated = False,
                      dry_run = False,
                      job_id=None):
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"文件路径{str(file)}")
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            print(f"AI生成声明：{ai_generated}")
            print(f"仅预览不发布：{dry_run}")
            kwargs = dict(
                title=title,
                file_path=str(file),
                tags=tags,
                publish_date=publish_datetimes[index],
                account_file=cookie,
                thumbnail_landscape_path=thumbnail_path,
                productLink=productLink,
                productTitle=productTitle,
                ai_generated=ai_generated,
                dry_run=dry_run,
                publish_strategy=(
                    DOUYIN_PUBLISH_STRATEGY_SCHEDULED
                    if enableTimer
                    else DOUYIN_PUBLISH_STRATEGY_IMMEDIATE
                ),
            )
            if dry_run:
                kwargs["headless"] = False

            def _do_upload(kw=kwargs):
                app = DouYinVideo(**kw)
                asyncio.run(app.douyin_upload_video(), debug=False)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)


def post_video_ks(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, dry_run=False, ai_generated=False, job_id=None):
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"文件路径{str(file)}")
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            print(f"AI生成声明：{ai_generated}")
            print(f"仅预览不发布：{dry_run}")
            kwargs = dict(
                title=title,
                file_path=str(file),
                tags=tags,
                publish_date=publish_datetimes[index],
                account_file=cookie,
                dry_run=dry_run,
                ai_generated=ai_generated,
            )
            if dry_run:
                kwargs["headless"] = False

            def _do_upload(kw=kwargs):
                app = KSVideo(**kw)
                asyncio.run(app.main(), debug=False)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)

def post_video_xhs(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, dry_run=False, ai_generated=False, job_id=None):
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    file_num = len(file_paths)
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(file_num, videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = 0
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            print(f"AI生成声明：{ai_generated}")
            print(f"仅预览不发布：{dry_run}")
            kwargs = dict(
                title=title,
                file_path=file,
                tags=tags,
                publish_date=publish_datetimes,
                account_file=cookie,
                dry_run=dry_run,
                ai_generated=ai_generated,
            )
            if dry_run:
                kwargs["headless"] = False

            def _do_upload(kw=kwargs):
                app = XiaoHongShuVideo(**kw)
                asyncio.run(app.main(), debug=False)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)



def post_video_baijiahao(title, files, tags, account_file, category=TencentZoneTypes.LIFESTYLE.value, enableTimer=False, videos_per_day=1, daily_times=None, start_days=0, dry_run=False, job_id=None):
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    for file in file_paths:
        if not file.exists():
            raise FileNotFoundError(f"视频文件不存在: {file}")
    for cookie in account_paths:
        if not cookie.exists():
            raise FileNotFoundError(f"Cookie 文件不存在: {cookie}")
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times, start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"🟢 百家号发布开始: 文件={file}, 账号={cookie}, dryRun={dry_run}", flush=True)
            print(f"标题：{title}", flush=True)
            print(f"Hashtag：{tags}", flush=True)

            def _do_upload(f=file, c=cookie, pdt=publish_datetimes[index]):
                app = BaiJiaHaoVideo(title, str(f), tags, pdt, str(c), dry_run=dry_run)
                if dry_run:
                    app.headless = False
                asyncio.run(app.main(), debug=False)
                print(f"✅ 百家号发布流程结束: {f}", flush=True)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)


def post_video_toutiao(title, files, tags, account_file, category=TencentZoneTypes.LIFESTYLE.value, enableTimer=False, videos_per_day=1, daily_times=None, start_days=0, dry_run=False, job_id=None):
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times, start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie in enumerate(account_paths):
            print(f"文件路径{str(file)}")
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            print(f"仅预览不发布：{dry_run}")

            def _do_upload(f=file, c=cookie, pdt=publish_datetimes[index]):
                app = TouTiaoVideo(title, str(f), tags, pdt, c, dry_run=dry_run)
                if dry_run:
                    app.headless = False
                asyncio.run(app.main(), debug=False)

            run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)


def post_article_toutiao(
    title,
    body,
    tags,
    account_file,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    dry_run=False,
    cover_path="",
    work_statements=None,
    job_id=None,
):
    """今日头条图文文章发布（contentType=article）。

    cover_path: 前端 /upload 返回的文件名（位于 videoFile/），或绝对/相对路径。
    单张封面最大 20MB，建议 JPEG/PNG。
    work_statements: 作品声明（单选）。可传字符串，或仅含一项的列表，如 "引用AI" / ["引用AI"]。
    """
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    cover = None
    if cover_path:
        raw = str(cover_path).strip()
        # 兼容 "videoFile/xxx.jpg" 或仅文件名
        name_only = Path(raw.replace("\\", "/")).name
        candidates = [
            Path(raw),
            Path(BASE_DIR / "videoFile" / raw),
            Path(BASE_DIR / "videoFile" / name_only),
            Path(BASE_DIR / raw),
        ]
        for cand in candidates:
            try:
                if cand.is_file():
                    cover = str(cand.resolve())
                    break
            except Exception:
                continue
        if not cover:
            print(f"⚠️ 封面路径未找到，将跳过封面: {cover_path}", flush=True)
        else:
            size = Path(cover).stat().st_size
            if size > 20 * 1024 * 1024:
                print(f"⚠️ 封面超过 20MB（{size} bytes），将跳过: {cover}", flush=True)
                cover = None

    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(1, videos_per_day, daily_times, start_days)
        publish_date = publish_datetimes[0]
    else:
        publish_date = 0

    article_label = f"[文章]{(title or '').strip() or 'untitled'}"
    for cookie_idx, cookie in enumerate(account_paths):
        print(f"cookie文件：{cookie}", flush=True)
        print(f"文章标题：{title}", flush=True)
        print(f"正文长度：{len(body or '')}", flush=True)
        print(f"Hashtag：{tags}", flush=True)
        print(f"封面：{cover}", flush=True)
        print(f"作品声明：{work_statements}", flush=True)
        print(f"仅预览不发布：{dry_run}", flush=True)

        def _do_upload(c=cookie):
            app = TouTiaoArticle(
                title=title,
                body=body,
                tags=tags or [],
                publish_date=publish_date,
                account_file=c,
                dry_run=dry_run,
                cover_path=cover,
                work_statements=work_statements,
            )
            if dry_run:
                app.headless = False
            asyncio.run(app.main(), debug=False)

        run_tracked_upload(job_id, article_label, account_names[cookie_idx], _do_upload)


def post_article_baijiahao(
    title,
    body,
    tags,
    account_file,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    dry_run=False,
    cover_path="",
    ai_generated=False,
    job_id=None,
):
    """百家号图文文章发布（contentType=article）。

    Args:
        title: 文章标题（2-64字）
        body: 文章正文内容
        tags: 文章标签列表
        account_file: Cookie文件名列表
        enableTimer: 是否启用定时发布
        videos_per_day: 每天发布数量
        daily_times: 每天发布时间段
        start_days: 开始天数偏移
        dry_run: 是否仅预览不发布
        cover_path: 封面图片路径（百家号图文必填）
        ai_generated: 是否勾选「采用AI生成内容」
    """
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    cover = None
    if cover_path:
        raw = str(cover_path).strip()
        name_only = Path(raw.replace("\\", "/")).name
        candidates = [
            Path(raw),
            Path(BASE_DIR / "videoFile" / raw),
            Path(BASE_DIR / "videoFile" / name_only),
            Path(BASE_DIR / raw),
        ]
        for cand in candidates:
            try:
                if cand.is_file():
                    cover = str(cand.resolve())
                    break
            except Exception:
                continue
        if not cover:
            print(f"⚠️ 封面路径未找到: {cover_path}", flush=True)
        else:
            size = Path(cover).stat().st_size
            if size > 5 * 1024 * 1024:
                print(f"⚠️ 封面超过 5MB（{size} bytes）: {cover}", flush=True)
                cover = None

    if not cover:
        raise ValueError("百家号图文展示封面不能为空，请上传 JPEG/PNG 封面（单张最大 5MB）")

    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(1, videos_per_day, daily_times, start_days)
        publish_date = publish_datetimes[0]
    else:
        publish_date = 0

    article_label = f"[文章]{(title or '').strip() or 'untitled'}"
    for cookie_idx, cookie in enumerate(account_paths):
        print(f"🟢 百家号图文文章发布开始: 账号={cookie}, dryRun={dry_run}", flush=True)
        print(f"文章标题：{title}", flush=True)
        print(f"正文长度：{len(body or '')} 字符", flush=True)
        print(f"Hashtag：{tags}", flush=True)
        print(f"封面：{cover}", flush=True)

        def _do_upload(c=cookie):
            app = BaiJiaHaoArticle(
                title=title,
                body=body,
                tags=tags or [],
                publish_date=publish_date,
                account_file=str(c),
                dry_run=dry_run,
                cover_path=cover,
                ai_generated=ai_generated,
            )
            if dry_run:
                app.headless = False
            asyncio.run(app.main(), debug=False)
            print(f"✅ 百家号图文文章发布流程结束", flush=True)

        run_tracked_upload(job_id, article_label, account_names[cookie_idx], _do_upload)


def post_article_sohu(
    title,
    body,
    tags,
    account_file,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    dry_run=False,
    cover_path="",
    info_source=None,
    cover_paths=None,
    job_id=None,
):
    """搜狐号图文文章发布（type=8, contentType=article）。

    cover_path / cover_paths: 封面图片。可多张；单张最大 10MB；jpg/jpeg/png/gif。
    info_source: 信息来源单选。无特别声明 / 引用声明 / 包含AI创作内容 / 包含虚构创作。
    """
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]

    raw_covers = []
    if cover_paths:
        if isinstance(cover_paths, str):
            raw_covers = [x.strip() for x in cover_paths.split(",") if x.strip()]
        else:
            try:
                raw_covers = [str(x).strip() for x in cover_paths if str(x).strip()]
            except TypeError:
                raw_covers = [str(cover_paths).strip()] if str(cover_paths).strip() else []
    if cover_path and str(cover_path).strip():
        one = str(cover_path).strip()
        if one not in raw_covers:
            raw_covers.insert(0, one)

    resolved_covers = []
    for raw in raw_covers:
        name_only = Path(raw.replace("\\", "/")).name
        candidates = [
            Path(raw),
            Path(BASE_DIR / "videoFile" / raw),
            Path(BASE_DIR / "videoFile" / name_only),
            Path(BASE_DIR / raw),
        ]
        found = None
        for cand in candidates:
            try:
                if cand.is_file():
                    found = cand
                    break
            except Exception:
                continue
        if not found:
            print(f"⚠️ 封面路径未找到，将跳过: {raw}", flush=True)
            continue
        size = found.stat().st_size
        if size > 10 * 1024 * 1024:
            print(f"⚠️ 封面超过 10MB（{size} bytes），将跳过: {found}", flush=True)
            continue
        if found.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif"}:
            print(f"⚠️ 封面格式不支持（需 jpg/jpeg/png/gif），将跳过: {found}", flush=True)
            continue
        resolved_covers.append(str(found.resolve()))

    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(1, videos_per_day, daily_times, start_days)
        publish_date = publish_datetimes[0]
    else:
        publish_date = 0

    article_label = f"[文章]{(title or '').strip() or 'untitled'}"
    for cookie_idx, cookie in enumerate(account_paths):
        print(f"🟢 搜狐号图文文章发布开始: 账号={cookie}, dryRun={dry_run}", flush=True)
        print(f"文章标题：{title}", flush=True)
        print(f"正文长度：{len(body or '')}", flush=True)
        print(f"Hashtag：{tags}", flush=True)
        print(f"封面数量：{len(resolved_covers)} {resolved_covers}", flush=True)
        print(f"信息来源：{info_source}", flush=True)
        print(f"仅预览不发布：{dry_run}", flush=True)

        def _do_upload(c=cookie):
            app = SoHuArticle(
                title=title,
                body=body,
                tags=tags or [],
                publish_date=publish_date,
                account_file=c,
                dry_run=dry_run,
                cover_path=resolved_covers[0] if resolved_covers else None,
                cover_paths=resolved_covers,
                info_source=info_source,
            )
            if dry_run:
                app.headless = False
            asyncio.run(app.main(), debug=False)
            print(f"✅ 搜狐号图文文章发布流程结束", flush=True)

        run_tracked_upload(job_id, article_label, account_names[cookie_idx], _do_upload)


def post_article_zhihu(
    title,
    body,
    tags,
    account_file,
    enableTimer=False,
    videos_per_day=1,
    daily_times=None,
    start_days=0,
    dry_run=False,
    cover_path="",
    creation_statement=None,
    job_id=None,
):
    """知乎文章发布（type=9, contentType=article）。

    cover_path: 可选封面图片，单张最大 10MB；jpg/jpeg/png。
    creation_statement: 创作声明下拉。默认「无声明」。
    """
    account_names = [str(a) for a in account_file]
    account_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]

    cover = None
    if cover_path and str(cover_path).strip():
        raw = str(cover_path).strip()
        name_only = Path(raw.replace("\\", "/")).name
        candidates = [
            Path(raw),
            Path(BASE_DIR / "videoFile" / raw),
            Path(BASE_DIR / "videoFile" / name_only),
            Path(BASE_DIR / raw),
        ]
        found = None
        for cand in candidates:
            try:
                if cand.is_file():
                    found = cand
                    break
            except Exception:
                continue
        if not found:
            print(f"⚠️ 封面路径未找到，将跳过: {raw}", flush=True)
        else:
            size = found.stat().st_size
            if size > 10 * 1024 * 1024:
                print(f"⚠️ 封面超过 10MB（{size} bytes），将跳过: {found}", flush=True)
            elif found.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                print(f"⚠️ 封面格式不支持（需 jpg/jpeg/png），将跳过: {found}", flush=True)
            else:
                cover = str(found.resolve())

    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(1, videos_per_day, daily_times, start_days)
        publish_date = publish_datetimes[0]
    else:
        publish_date = 0

    article_label = f"[文章]{(title or '').strip() or 'untitled'}"
    for cookie_idx, cookie in enumerate(account_paths):
        print(f"🟢 知乎文章发布开始: 账号={cookie}, dryRun={dry_run}", flush=True)
        print(f"文章标题：{title}", flush=True)
        print(f"正文长度：{len(body or '')}", flush=True)
        print(f"Hashtag：{tags}", flush=True)
        print(f"封面：{cover}", flush=True)
        print(f"创作声明：{creation_statement}", flush=True)
        print(f"仅预览不发布：{dry_run}", flush=True)

        def _do_upload(c=cookie):
            app = ZhiHuArticle(
                title=title,
                body=body,
                tags=tags or [],
                publish_date=publish_date,
                account_file=c,
                dry_run=dry_run,
                cover_path=cover,
                creation_statement=creation_statement,
            )
            if dry_run:
                app.headless = False
            asyncio.run(app.main(), debug=False)
            print(f"✅ 知乎文章发布流程结束", flush=True)

        run_tracked_upload(job_id, article_label, account_names[cookie_idx], _do_upload)


def _build_bilibili_creation_extra_fields(creation_statement):
    """构建 biliup --extra-fields JSON。creation_statement 为 B 站创作声明 id。"""
    if creation_statement is None or creation_statement == "":
        return None
    try:
        statement_id = int(creation_statement)
    except (TypeError, ValueError):
        return None
    # 合法 id：-1 无需标注；1 AI；2 虚构演绎；3 营销；4 个人观点
    if statement_id not in (-1, 1, 2, 3, 4):
        print(f"⚠️ 忽略非法创作声明 id: {statement_id}", flush=True)
        return None
    import json
    return json.dumps({"creation_statement": {"id": statement_id}}, ensure_ascii=False, separators=(",", ":"))


def post_video_bilibili(title, files, tags, account_file, category=None, enableTimer=False, videos_per_day=1, daily_times=None, start_days=0, dry_run=False, creation_statement=None, job_id=None):
    """通过biliup CLI发布Bilibili视频

    creation_statement: B站创作声明 id
      -1 内容无需标注
       1 含 AI 生成内容
       2 含虚构演绎内容
       3 内容含营销信息
       4 个人观点，仅供参考
      None 不传（不声明）
    """
    file_names = [str(f) for f in files]
    account_names = [str(a) for a in account_file]
    account_file_paths = [Path(BASE_DIR / "cookiesFile" / file) for file in account_names]
    file_paths = [Path(BASE_DIR / "videoFile" / file) for file in file_names]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(file_paths), videos_per_day, daily_times, start_days)
    else:
        publish_datetimes = [0 for i in range(len(file_paths))]
    # Bilibili分区ID，默认21（日常）
    # 注意：Web 发布页的 category 目前只表示视频号原创，B站这里通常会落到默认 21
    tid = int(category) if category else 21
    extra_fields = _build_bilibili_creation_extra_fields(creation_statement)
    print(
        f"🎬 开始B站发布: files={len(file_paths)}, accounts={len(account_file_paths)}, "
        f"tid={tid}, dry_run={dry_run}, creation_statement={creation_statement}",
        flush=True,
    )
    for index, file in enumerate(file_paths):
        for cookie_idx, cookie_file in enumerate(account_file_paths):
            print(f"文件路径{str(file)}", flush=True)
            print(f"视频文件名：{file}", flush=True)
            print(f"cookie文件：{cookie_file}", flush=True)
            print(f"标题：{title}", flush=True)
            print(f"Hashtag：{tags}", flush=True)
            print(f"创作声明：{creation_statement}", flush=True)
            print(f"仅预览不发布：{dry_run}", flush=True)

            def _do_upload(f=file, c=cookie_file, pdt=publish_datetimes[index]):
                if not f.exists():
                    raise FileNotFoundError(f"视频文件不存在: {f}")
                if not c.exists():
                    raise FileNotFoundError(f"B站 cookie 文件不存在: {c}")
                arguments = [
                    "-u", str(c),
                    "upload", str(f),
                    "--title", title,
                    "--desc", title,
                    "--tid", str(tid),
                    "--copyright", "1",
                ]
                if tags:
                    arguments.extend(["--tag", ",".join(tags)])
                if pdt != 0:
                    import datetime
                    if isinstance(pdt, datetime.datetime):
                        dtime = str(int(pdt.timestamp()))
                    else:
                        dtime = str(int(pdt))
                    arguments.extend(["--dtime", dtime])
                if extra_fields:
                    arguments.extend(["--extra-fields", extra_fields])
                print(f"🚀 调用 biliup: {' '.join(arguments)}", flush=True)
                result = run_biliup_command(arguments)
                stdout_text = (result.stdout or "").strip()
                stderr_text = (result.stderr or "").strip()
                if stdout_text:
                    print(f"[biliup stdout]\n{stdout_text}", flush=True)
                if stderr_text:
                    print(f"[biliup stderr]\n{stderr_text}", flush=True)
                if result.returncode != 0:
                    error_msg = stderr_text or stdout_text
                    print(f"❌ Bilibili上传失败 (code={result.returncode}): {error_msg}", flush=True)
                    raise RuntimeError(error_msg or "Bilibili upload failed")
                print("✅ Bilibili上传成功", flush=True)

            if dry_run:
                print("🛑 【仅预览不发布】B站走 biliup CLI，无浏览器可预览，已跳过实际上传", flush=True)
                if job_id is not None:
                    from myUtils.publish_job import RESULT_SKIPPED, update_publish_result
                    update_publish_result(
                        job_id,
                        file_names[index],
                        account_names[cookie_idx],
                        RESULT_SKIPPED,
                        "仅预览不发布，已跳过",
                    )
            else:
                run_tracked_upload(job_id, file_names[index], account_names[cookie_idx], _do_upload)


# post_video("333",["demo.mp4"],"d","d")
# post_video_DouYin("333",["demo.mp4"],"d","d")
