import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        (self.root / "db").mkdir(parents=True)
        self.script = self.root / "db" / "createTable.py"
        shutil.copyfile(Path(__file__).resolve().parents[1] / "db" / "createTable.py", self.script)

    def initialize(self, cwd):
        subprocess.run(
            [sys.executable, "-B", str(self.script)],
            cwd=cwd,
            check=True,
            capture_output=True,
        )

    def test_initialization_uses_checkout_path_from_any_working_directory(self):
        for cwd in (self.root, self.root / "db", Path(self.temp.name)):
            with self.subTest(cwd=cwd):
                self.initialize(cwd)
                self.assertTrue((self.root / "db" / "database.db").is_file())
                self.assertFalse((self.root / "database.db").exists())
                self.assertFalse((Path(self.temp.name) / "database.db").exists())
                for name in ("cookies", "cookiesFile", "videoFile"):
                    self.assertTrue((self.root / name).is_dir())

    def test_reinitialization_preserves_existing_accounts(self):
        self.initialize(self.root)
        database = self.root / "db" / "database.db"
        with closing(sqlite3.connect(database)) as conn, conn:
            conn.execute(
                "INSERT INTO user_info (type, filePath, userName) VALUES (?, ?, ?)",
                (3, "example.json", "example"),
            )
        self.initialize(Path(self.temp.name))
        with closing(sqlite3.connect(database)) as conn:
            self.assertEqual(conn.execute("SELECT userName FROM user_info").fetchall(), [("example",)])
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"user_info", "file_records", "content_stats", "publish_jobs", "publish_results"} <= tables)


if __name__ == "__main__":
    unittest.main()
