"""Task storage for Tasker.

This module is the SINGLE SOURCE OF TRUTH. Both the CLI (cli.py) and the
MCP server (codex/mcp/tasker_mcp_server.py) must go through TaskStore, so
they can never drift apart.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

VALID_PRIORITIES = ("low", "normal", "high")
VALID_STATUS = ("todo", "doing", "done")

# Default: <project>/data/tasks.json
DEFAULT_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tasks.json"


def resolve_data_file() -> Path:
    """TASKER_DATA_FILE environment variable wins; otherwise the package default."""
    env = os.environ.get("TASKER_DATA_FILE")
    return Path(env) if env else DEFAULT_DATA_FILE


class StoreError(Exception):
    """Raised for any user-facing storage/validation failure."""


def normalize_due_date(value: str | None) -> str | None:
    """Validate and normalize an optional due date (YYYY-MM-DD)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise StoreError("due_date must use YYYY-MM-DD format")
    value = value.strip()
    if not value:
        raise StoreError("due_date must use YYYY-MM-DD format")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise StoreError("due_date must use YYYY-MM-DD format") from exc
    return parsed.isoformat()


class TaskStore:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path else resolve_data_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"tasks file is corrupt: {exc}") from exc
        if not isinstance(data, list):
            raise StoreError("tasks file must contain a JSON list")
        return data

    def _save(self, tasks: list[dict]) -> None:
        # Atomic write: tmp file in the same directory, then os.replace.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def add(
        self, title: str, priority: str = "normal", due_date: str | None = None
    ) -> dict:
        title = (title or "").strip()
        if not title:
            raise StoreError("title must not be empty")
        if priority not in VALID_PRIORITIES:
            raise StoreError(f"priority must be one of {VALID_PRIORITIES}")
        due_date = normalize_due_date(due_date)
        tasks = self._load()
        task = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "priority": priority,
            "due_date": due_date,
            "status": "todo",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        tasks.append(task)
        self._save(tasks)
        return task

    def list(self, status: str | None = None) -> list[dict]:
        tasks = self._load()
        if status:
            if status not in VALID_STATUS:
                raise StoreError(f"status must be one of {VALID_STATUS}")
            tasks = [t for t in tasks if t["status"] == status]
        return tasks

    def set_status(self, task_id: str, status: str) -> dict:
        if status not in VALID_STATUS:
            raise StoreError(f"status must be one of {VALID_STATUS}")
        tasks = self._load()
        for t in tasks:
            if t["id"] == task_id:
                t["status"] = status
                self._save(tasks)
                return t
        raise StoreError(f"no task with id {task_id!r}")

    def delete(self, task_id: str) -> dict:
        """Remove a task by id and return it. Raises StoreError if it is absent."""
        tasks = self._load()
        for i, t in enumerate(tasks):
            if t["id"] == task_id:
                removed = tasks.pop(i)
                self._save(tasks)
                return removed
        raise StoreError(f"no task with id {task_id!r}")

    def stats(self) -> dict:
        tasks = self._load()
        out: dict = {s: 0 for s in VALID_STATUS}
        out["total"] = len(tasks)
        for t in tasks:
            out[t["status"]] = out.get(t["status"], 0) + 1
        return out