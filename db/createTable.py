"""Initialize the project database and runtime directories without deleting data."""
import sqlite3
from contextlib import closing
from pathlib import Path


def initialize_database() -> Path:
    root = Path(__file__).resolve().parent.parent
    for name in ("db", "cookies", "cookiesFile", "videoFile"):
        (root / name).mkdir(parents=True, exist_ok=True)
    db_file = root / "db" / "database.db"
    with closing(sqlite3.connect(db_file)) as conn, conn:
        cursor = conn.cursor()
        # 创建账号记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            filePath TEXT NOT NULL,  -- 存储文件路径
            userName TEXT NOT NULL,
            status INTEGER DEFAULT 0
        )
        ''')

        # 创建文件记录表
        cursor.execute('''CREATE TABLE IF NOT EXISTS file_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- 唯一标识每条记录
            filename TEXT NOT NULL,               -- 文件名
            filesize REAL,                     -- 文件大小（单位：MB）
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 上传时间（SQLite 存 UTC，接口返回时转本地时间）
            file_path TEXT                        -- 文件路径
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT,
            cover_url TEXT,
            status TEXT,
            published_at TEXT,
            play_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            collect_count INTEGER DEFAULT 0,
            completion_rate REAL,
            avg_play_duration_sec REAL,
            bounce_rate_2s REAL,
            completion_rate_5s REAL,
            avg_play_percent REAL,
            traffic_sources_json TEXT,
            extra_json TEXT,
            boost_play_count INTEGER,
            boost_reason TEXT,
            synced_at TEXT NOT NULL,
            raw_json TEXT,
            UNIQUE(platform, account_id, item_id)
        )
        ''')

        cursor.execute('''
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
        ''')

        cursor.execute('''
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
        ''')


    return db_file


if __name__ == "__main__":
    database = initialize_database()
    print(f"Database ready: {database}")
