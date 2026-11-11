from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.storage import ProjectStore


class StorageTests(unittest.TestCase):
    def test_project_and_analysis_are_persisted(self):
        database = ROOT / "work" / f"test_storage_{uuid4().hex}.sqlite3"
        database.parent.mkdir(exist_ok=True)
        try:
            store = ProjectStore(database)
            store.initialize()
            project = store.create_project("测试项目")
            store.save_analysis(
                project.id,
                "correlation",
                {"method": "pearson"},
                {"n": 20, "coefficient": 0.5},
            )
            projects = store.list_projects()
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0].name, "测试项目")
            self.assertTrue(database.exists())
            backup = store.backup_bytes()
            self.assertTrue(backup.startswith(b"SQLite format 3\x00"))
            self.assertTrue(store.clear_project(project.id))
            self.assertEqual(store.list_projects(), [])
        finally:
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(database) + suffix)
                if candidate.exists():
                    candidate.unlink()


if __name__ == "__main__":
    unittest.main()
