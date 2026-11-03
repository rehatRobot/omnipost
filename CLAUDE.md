## Project Overview

OmniPost is a multi-platform content publishing tool based on social-auto-upload. Its Python distribution remains `social-auto-upload`, and the CLI command remains `sau`.

- Web is the maintained and recommended interface for accounts, materials, publishing tasks and statistics.
- CLI is retained for compatibility and has not been maintained in sync with this Web update. It exposes `douyin`, `kuaishou`, `xiaohongshu`, `bilibili` and `tencent` (WeChat Channels).
- examples and Skills are retained references and have not been maintained in sync with this Web update. Prefer Web workflows unless the user explicitly requests another entrypoint.
- Four bundled Skills cover Douyin, Kuaishou, Xiaohongshu and Bilibili. There is no dedicated Tencent Skill or `sau skill install` command.
- Browser workflows use Patchright / Playwright; Bilibili uses biliup. Content support differs by platform and entrypoint.

Use [README](README.md) for Web installation and the Web capability table, [docs/status.md](docs/status.md) for verification boundaries, and [docs/legacy-web.md](docs/legacy-web.md) for Web coverage. Implemented features are not proof of successful real-account publishing.

## Building and Running

Follow the installation section in README.md and troubleshooting in docs/install.md.

1. Copy conf.example.py to conf.py if it does not exist. Preserve existing local configuration.
2. Install Python 3.12 dependencies with `uv sync --locked --extra web --python 3.12`.
3. Install Google Chrome stable and run `uv run --no-sync playwright install chromium` for Web account checks.
4. Run `uv run --no-sync python db/createTable.py`. It is safe to repeat and does not delete existing records.
5. Install frontend dependencies with `npm --prefix sau_frontend ci`.
6. In separate terminals, run `uv run --no-sync python sau_backend.py` and `npm --prefix sau_frontend run dev -- --host 127.0.0.1 --strictPort`.
7. Open http://127.0.0.1:5173/. Backend, development and preview servers bind to 127.0.0.1 by default. Stop both terminals with Ctrl+C.

For CLI-only installation, omit `--extra web` and use `uv run --no-sync sau ...`. The upload action is `upload-video` or `upload-note`; consult `uv run --no-sync sau --help` for supported commands.

## Development Conventions

*   The backend code is located in the root directory and the `myUtils` and `uploader` directories.
*   The frontend code is located in the `sau_frontend` directory.
*   The project uses a SQLite database for data storage. The database file is located at `db/database.db`.
*   The `conf.example.py` file should be copied to `conf.py` and configured with the appropriate settings.
*   Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`; `requirements.txt` is a pip compatibility entry point.
*   The `package.json` file in the `sau_frontend` directory lists the frontend dependencies.
