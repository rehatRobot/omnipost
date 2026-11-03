"""导出指定平台账号（user_info 元数据 + cookiesFile 登录态）为可移交 zip。

用法：
  python scripts/export_accounts.py --type 6
  python scripts/export_accounts.py --type 6 --out transfer/bilibili_accounts.zip
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM_NAMES = {
    1: "xiaohongshu",
    2: "tencent",
    3: "douyin",
    4: "kuaishou",
    5: "baijiahao",
    6: "bilibili",
    7: "toutiao",
    8: "sohu",
    9: "zhihu",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="导出账号 cookie 数据包")
    parser.add_argument("--type", type=int, required=True, help="平台 type，B站=6")
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
    parser.add_argument("--out", default="", help="输出 zip 路径（可选）")
    args = parser.parse_args()

    db = Path(args.db)
    cookies_dir = Path(args.cookies_dir)
    if not db.is_file():
        raise SystemExit(f"数据库不存在: {db}")
    if not cookies_dir.is_dir():
        raise SystemExit(f"cookie 目录不存在: {cookies_dir}")

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT type, filePath, userName, status FROM user_info WHERE type = ? ORDER BY id",
            (args.type,),
        ).fetchall()

    if not rows:
        raise SystemExit(f"未找到 type={args.type} 的账号")

    accounts = []
    missing = []
    for row in rows:
        file_path = row["filePath"]
        cookie_file = cookies_dir / file_path
        if not cookie_file.is_file():
            missing.append(file_path)
            continue
        accounts.append(
            {
                "type": int(row["type"]),
                "filePath": file_path,
                "userName": row["userName"],
                "status": int(row["status"] or 0),
            }
        )

    if missing:
        print("警告：以下 cookie 文件缺失，已跳过：")
        for name in missing:
            print(f"  - {name}")
    if not accounts:
        raise SystemExit("没有可导出的账号（cookie 文件均缺失）")

    platform = PLATFORM_NAMES.get(args.type, f"type{args.type}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else ROOT / "transfer" / f"{platform}_accounts_{stamp}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "platform_type": args.type,
        "platform_name": platform,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "accounts": accounts,
    }

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "accounts.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for acc in accounts:
            src = cookies_dir / acc["filePath"]
            zf.write(src, arcname=f"cookies/{acc['filePath']}")

    print(f"已导出 {len(accounts)} 个账号 -> {out}")
    for acc in accounts:
        print(f"  - {acc['userName']} ({acc['filePath']})")
    print("注意：zip 内含登录凭证，请勿公开传播，传完后建议双方删除。")


if __name__ == "__main__":
    main()
