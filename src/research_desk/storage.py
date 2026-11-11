from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectRecord:
    id: int
    name: str
    created_at: str
    updated_at: str


def default_workspace_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "ResearchDesk"


class ProjectStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    analysis_type TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                """
            )

    def create_project(self, name: str) -> ProjectRecord:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO projects(name, created_at, updated_at) VALUES (?, ?, ?)",
                (name.strip(), now, now),
            )
            project_id = int(cursor.lastrowid)
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> ProjectRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, name, created_at, updated_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError("项目不存在。")
        return ProjectRecord(*row)

    def list_projects(self) -> list[ProjectRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, name, created_at, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [ProjectRecord(*row) for row in rows]

    def save_analysis(
        self,
        project_id: int,
        analysis_type: str,
        parameters: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO analyses(project_id, analysis_type, parameters_json, result_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    analysis_type,
                    json.dumps(parameters, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    now,
                ),
            )
            connection.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )

    def backup_bytes(self) -> bytes:
        target = sqlite3.connect(":memory:")
        try:
            with self._connection() as source:
                source.backup(target)
            return target.serialize()
        finally:
            target.close()

    def clear_project(self, project_id: int) -> bool:
        with self._connection() as connection:
            connection.execute("DELETE FROM analyses WHERE project_id = ?", (project_id,))
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
