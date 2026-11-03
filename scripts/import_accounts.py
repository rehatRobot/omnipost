"""从 export_accounts.py 生成的 zip 导入账号到本机项目。

用法：
  python scripts/import_accounts.py transfer/bilibili_accounts_xxx.zip
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_package(zip_path: Path, extract_dir: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    manifest_path = extract_dir / "accounts.json"
    if not manifest_path.is_file():
        raise SystemExit("zip 内缺少 accounts.json，不是本工具导出的包")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="导入账号 cookie 数据包")
    parser.add_argument("zip", help="export_accounts.py 导出的 zip")
    parser.add_argument(
        "--db",
        default=str(ROOT / "db" / "database.db"),
        help="SQLite 路径",
    )
    parser.add_argument(
        "--cookies-dir",
        default=str(ROOT / "cookiesFile"),
        help="cookie 目录",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="同名同平台账号已存在时覆盖 cookie",
    )
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.is_file():
        raise SystemExit(f"zip 不存在: {zip_path}")

    db = Path(args.db)
    cookies_dir = Path(args.cookies_dir)
    cookies_dir.mkdir(parents=True, exist_ok=True)
    if not db.is_file():
        raise SystemExit(f"数据库不存在: {db}（请先 python db/createTable.py）")

    with tempfile.TemporaryDirectory(prefix="sau_import_") as tmp:
        extract_dir = Path(tmp)
        manifest = _load_package(zip_path, extract_dir)
        accounts = manifest.get("accounts") or []
        if not accounts:
            raise SystemExit("accounts.json 中没有账号")

        imported = 0
        skipped = 0
        updated = 0

        with sqlite3.connect(db) as conn:
            cur = conn.cursor()
            for acc in accounts:
                platform_type = int(acc["type"])
                user_name = acc["userName"]
                file_name = acc["filePath"]
                status = int(acc.get("status") or 1)
                src = extract_dir / "cookies" / file_name
                if not src.is_file():
                    print(f"跳过（缺 cookie 文件）: {user_name} -> {file_name}")
                    skipped += 1
                    continue

                cur.execute(
                    "SELECT id, filePath FROM user_info WHERE type = ? AND userName = ?",
                    (platform_type, user_name),
                )
                row = cur.fetchone()
                dst = cookies_dir / file_name

                if row:
                    if not args.overwrite:
                        print(f"已存在，跳过: type={platform_type} name={user_name}（加 --overwrite 可覆盖）")
                        skipped += 1
                        continue
                    old_id, old_path = row
                    shutil.copy2(src, dst)
                    cur.execute(
                        "UPDATE user_info SET filePath = ?, status = ? WHERE id = ?",
                        (file_name, status, old_id),
                    )
                    if old_path and old_path != file_name:
                        old_file = cookies_dir / str(old_path)
                        if old_file.is_file() and old_file.resolve() != dst.resolve():
                            try:
                                old_file.unlink()
                            except OSError:
                                pass
                    print(f"已覆盖: id={old_id} type={platform_type} name={user_name}")
                    updated += 1
                else:
                    # 避免覆盖同事本地同名但无关的 cookie 文件
                    if dst.exists():
                        stem = Path(file_name).stem
                        suffix = Path(file_name).suffix or ".json"
                        i = 1
                        while True:
                            candidate = cookies_dir / f"{stem}_imported{i}{suffix}"
                            if not candidate.exists():
                                dst = candidate
                                file_name = candidate.name
                                break
                            i += 1
                    shutil.copy2(src, dst)
                    cur.execute(
                        "INSERT INTO user_info (type, filePath, userName, status) VALUES (?, ?, ?, ?)",
                        (platform_type, file_name, user_name, status),
                    )
                    print(
                        f"已新增: id={cur.lastrowid} type={platform_type} name={user_name} file={file_name}"
                    )
                    imported += 1
            conn.commit()

    print(
        f"完成：新增 {imported}，覆盖 {updated}，跳过 {skipped}。"
        "刷新前端「账号管理」即可看到。"
    )


if __name__ == "__main__":
    main()
