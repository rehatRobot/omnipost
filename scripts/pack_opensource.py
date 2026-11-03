"""Build a clean open-source source archive (no secrets / local runtime data)."""
from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAMP = date.today().strftime("%Y%m%d")
ARCHIVE_NAME = f"social-auto-upload-opensource-{STAMP}.zip"
PREFIX = f"social-auto-upload-{STAMP}"

# Top-level / path prefixes to skip entirely
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    ".cursor",
    ".worktrees",
    ".learnings",
    ".uv-cache",
    "cookies",
    "cookiesFile",
    "uploadFile",
    "videoFile",
    "transfer",
    "logs",
    "dist",
    "build",
    ".vite",
    "htmlcov",
    "coverage",
    "scripts_dev",
}

SKIP_FILE_NAMES = {
    "conf.py",
    "database.db",
    "qrcode.png",
    ".DS_Store",
    "Thumbs.db",
    ".env",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".7z",
    ".rar",
}

# Unreferenced legacy screenshots / QR assets are not part of the source release.
SKIP_RELATIVE_PATHS = {
    "media/20231009111131.png",
    "media/20231009111214.png",
    "media/edan-qrcode.png",
    "media/get_bili_cookie.png",
    "media/group-qr.png",
    "media/tk_login.png",
    "media/xhs_error_cookie.png",
    "static/chilltion.png",
    "static/clawpower.png",
    "static/wechat.png",
}

# Local debug / personal artifacts
SKIP_NAME_GLOBS = (
    re.compile(r"^bjh_.*\.png$", re.I),
    re.compile(r"^tmp_.*$", re.I),
    re.compile(r"^probe_.*$", re.I),
    re.compile(r"^debug_.*$", re.I),
    re.compile(r"^database\.db\.empty-backup-.*$", re.I),
)

# Never ship real cookie / storage dumps
SKIP_PATH_REGEX = re.compile(
    r"(^|[/\\])("
    r"cookies([/\\]|$)|"
    r"cookiesFile([/\\]|$)|"
    r"uploadFile([/\\]|$)|"
    r"videoFile([/\\]|$)|"
    r"transfer([/\\]|$)|"
    r"logs([/\\]|$)|"
    r"\.worktrees([/\\]|$)|"
    r"\.uv-cache([/\\]|$)|"
    r"\.learnings([/\\]|$)|"
    r"scripts_dev([/\\]|$)|"
    r"db[/\\]database\.db$"
    r")",
    re.I,
)

SECRET_SCAN = re.compile(
    r"("
    r"access_token=[0-9a-f]{20,}|"
    r"SESSDATA\s*[:=]|"
    r"SECe[0-9a-f]{10,}|"
    r"DINGTALK_WEBHOOK_URL\s*=\s*\"https?://[^\"]+access_token=|"
    r"DINGTALK_SECRET\s*=\s*\"SEC"
    r")",
    re.I,
)


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel in SKIP_RELATIVE_PATHS:
        return True
    if SKIP_PATH_REGEX.search(rel.replace("\\", "/")):
        return True
    parts = path.relative_to(ROOT).parts
    if any(part in SKIP_DIR_NAMES or part.endswith(".egg-info") for part in parts[:-1]):
        return True
    if path.is_dir():
        return path.name in SKIP_DIR_NAMES or path.name.endswith(".egg-info")
    if any(part.endswith(".egg-info") for part in parts):
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if any(rx.match(path.name) for rx in SKIP_NAME_GLOBS):
        return True
    # root local config only — keep conf.example.py
    if path.parent == ROOT and path.name == "conf.py":
        return True
    return False


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        # skip this packager itself from archive? include is fine
        yield path


def resolve_out_dir() -> Path:
    # Optional override: python scripts/pack_opensource.py --out "C:/Users/.../Desktop"
    import sys

    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 >= len(sys.argv):
            raise SystemExit("usage: pack_opensource.py --out <directory>")
        return Path(sys.argv[idx + 1]).expanduser().resolve()
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop
    return ROOT / "dist"


def main() -> None:
    out_dir = resolve_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / ARCHIVE_NAME
    if archive_path.exists():
        archive_path.unlink()

    included = []
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for path in sorted(iter_files(), key=lambda p: p.as_posix().lower()):
            rel = path.relative_to(ROOT).as_posix()
            arcname = f"{PREFIX}/{rel}"
            zf.write(path, arcname)
            included.append(rel)

    # Verify no obvious secrets / forbidden paths inside zip
    bad = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = zf.namelist()
        for name in names:
            lower = name.lower()
            if any(
                x in lower
                for x in (
                    "/conf.py",
                    "/cookies/",
                    "/cookiesfile/",
                    "/database.db",
                    "/.venv/",
                    "/node_modules/",
                    "/logs/",
                    "/transfer/",
                    "/.uv-cache/",
                    "/.learnings/",
                    "/scripts_dev/",
                )
            ):
                # allow conf.example.py
                if not lower.endswith("/conf.example.py"):
                    bad.append(f"forbidden path: {name}")
            if "/debug_" in lower or lower.endswith("/qrcode.png") or lower.rsplit("/", 1)[-1].startswith("debug_"):
                bad.append(f"debug artifact: {name}")
            # scan text-ish files
            if lower.endswith((".py", ".js", ".vue", ".md", ".txt", ".ini", ".env", ".json", ".yml", ".yaml")):
                try:
                    data = zf.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                if SECRET_SCAN.search(data):
                    # conf.example with empty strings is OK; pattern requires non-empty token/SEC
                    bad.append(f"secret-like content: {name}")

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"archive: {archive_path}")
    print(f"files: {len(included)}")
    print(f"size_mb: {size_mb:.2f}")
    if bad:
        print("VERIFY FAILED:")
        for item in bad:
            print(" -", item)
        raise SystemExit(1)
    print("verify: OK (no conf.py / cookies / db / token patterns)")
    # print a short sample of top-level entries
    tops = sorted({p.split("/")[0] for p in included if "/" not in p} | {p.split("/")[0] for p in included})
    print("top entries:", ", ".join(sorted(tops)[:40]))


if __name__ == "__main__":
    main()
