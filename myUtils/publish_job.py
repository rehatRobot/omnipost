"""发布任务结果追踪：按「视频 × 账号」记录成败，供前端轮询。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from conf import BASE_DIR

JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCESS = "success"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_PARTIAL = "partial"

RESULT_PENDING = "pending"
RESULT_SUCCESS = "success"
RESULT_FAILED = "failed"
RESULT_SKIPPED = "skipped"


def _db_path() -> Path:
    return Path(BASE_DIR / "db" / "database.db")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def ensure_publish_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform INTEGER NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            total_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            finished_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            account_file TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            message TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES publish_jobs(id)
        )
        """
    )
    conn.commit()


def create_publish_job(
    platform: int,
    title: str,
    items: Sequence[tuple[str, str]],
) -> int:
    """创建任务并预写入 pending 结果行。items: (file_name, account_file)。"""
    now = _now()
    with sqlite3.connect(_db_path()) as conn:
        ensure_publish_tables(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO publish_jobs (platform, title, status, total_count, success_count, failed_count, created_at)
            VALUES (?, ?, ?, ?, 0, 0, ?)
            """,
            (int(platform), title or "", JOB_STATUS_RUNNING, len(items), now),
        )
        job_id = int(cur.lastrowid)
        for file_name, account_file in items:
            cur.execute(
                """
                INSERT INTO publish_results (job_id, file_name, account_file, status, message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, str(file_name), str(account_file), RESULT_PENDING, "", now),
            )
        conn.commit()
        return job_id


def update_publish_result(
    job_id: int,
    file_name: str,
    account_file: str,
    status: str,
    message: str = "",
) -> None:
    now = _now()
    with sqlite3.connect(_db_path()) as conn:
        ensure_publish_tables(conn)
        conn.execute(
            """
            UPDATE publish_results
            SET status = ?, message = ?, updated_at = ?
            WHERE job_id = ? AND file_name = ? AND account_file = ?
            """,
            (status, (message or "")[:2000], now, int(job_id), str(file_name), str(account_file)),
        )
        conn.commit()


def finalize_publish_job(job_id: int) -> dict[str, Any]:
    """根据结果汇总任务终态；仍为 pending 的记为 failed。"""
    now = _now()
    with sqlite3.connect(_db_path()) as conn:
        ensure_publish_tables(conn)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE publish_results
            SET status = ?, message = COALESCE(NULLIF(message, ''), ?), updated_at = ?
            WHERE job_id = ? AND status = ?
            """,
            (RESULT_FAILED, "任务结束时仍未完成（可能被中断）", now, int(job_id), RESULT_PENDING),
        )
        cur.execute(
            "SELECT status, COUNT(*) FROM publish_results WHERE job_id = ? GROUP BY status",
            (int(job_id),),
        )
        counts = {row[0]: int(row[1]) for row in cur.fetchall()}
        success_count = counts.get(RESULT_SUCCESS, 0) + counts.get(RESULT_SKIPPED, 0)
        failed_count = counts.get(RESULT_FAILED, 0)
        total = sum(counts.values())
        if failed_count == 0 and success_count > 0:
            status = JOB_STATUS_SUCCESS
        elif success_count == 0 and failed_count > 0:
            status = JOB_STATUS_FAILED
        elif success_count > 0 and failed_count > 0:
            status = JOB_STATUS_PARTIAL
        else:
            status = JOB_STATUS_FAILED
        cur.execute(
            """
            UPDATE publish_jobs
            SET status = ?, success_count = ?, failed_count = ?, total_count = ?, finished_at = ?
            WHERE id = ?
            """,
            (status, success_count, failed_count, total, now, int(job_id)),
        )
        conn.commit()
        return get_publish_job(job_id, conn=conn)


def get_publish_job(job_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    owns_conn = conn is None
    if owns_conn:
        conn = sqlite3.connect(_db_path())
    try:
        ensure_publish_tables(conn)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM publish_jobs WHERE id = ?", (int(job_id),))
        job_row = cur.fetchone()
        if not job_row:
            return None
        cur.execute(
            """
            SELECT r.*, u.userName AS account_name
            FROM publish_results r
            LEFT JOIN user_info u ON u.filePath = r.account_file
            WHERE r.job_id = ?
            ORDER BY r.id ASC
            """,
            (int(job_id),),
        )
        results = []
        for row in cur.fetchall():
            results.append(
                {
                    "id": row["id"],
                    "fileName": row["file_name"],
                    "accountFile": row["account_file"],
                    "accountName": row["account_name"] or Path(str(row["account_file"])).stem,
                    "status": row["status"],
                    "message": row["message"] or "",
                    "updatedAt": row["updated_at"],
                }
            )
        return {
            "jobId": job_row["id"],
            "platform": job_row["platform"],
            "title": job_row["title"] or "",
            "status": job_row["status"],
            "totalCount": job_row["total_count"],
            "successCount": job_row["success_count"],
            "failedCount": job_row["failed_count"],
            "createdAt": job_row["created_at"],
            "finishedAt": job_row["finished_at"],
            "results": results,
        }
    finally:
        if owns_conn:
            conn.close()


def build_video_job_items(
    file_list: Iterable[str],
    account_list: Iterable[str],
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for file_name in file_list:
        for account_file in account_list:
            items.append((str(file_name), str(account_file)))
    return items


def build_article_job_items(
    title: str,
    account_list: Iterable[str],
) -> list[tuple[str, str]]:
    label = f"[文章]{(title or '').strip() or 'untitled'}"
    return [(label, str(account_file)) for account_file in account_list]


def run_tracked_upload(job_id: int | None, file_name: str, account_file: str, upload_fn) -> None:
    """执行单次上传并写入结果；有 job_id 时失败不中断后续项。

    file_name / account_file 须与 create_publish_job 时写入的键一致（通常为前端相对名）。
    """
    file_key = str(file_name)
    account_key = str(account_file)
    try:
        upload_fn()
        if job_id is not None:
            update_publish_result(job_id, file_key, account_key, RESULT_SUCCESS, "发布成功")
    except Exception as exc:
        msg = str(exc) or exc.__class__.__name__
        print(f"❌ 发布失败: file={file_key}, account={account_key}, err={msg}", flush=True)
        if job_id is not None:
            update_publish_result(job_id, file_key, account_key, RESULT_FAILED, msg)
        else:
            raise
