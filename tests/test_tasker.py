import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tasker import cli as cli_mod  # noqa: E402
from tasker.store import StoreError, TaskStore  # noqa: E402


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "tasks.json"
        self.store = TaskStore(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_assigns_id_and_defaults(self):
        task = self.store.add("write docs")
        self.assertEqual(task["title"], "write docs")
        self.assertEqual(task["status"], "todo")
        self.assertEqual(task["priority"], "normal")
        self.assertIsNone(task["due_date"])
        self.assertEqual(len(task["id"]), 8)

    def test_add_stores_due_date(self):
        task = self.store.add("ship feature", due_date="2026-12-31")
        self.assertEqual(task["due_date"], "2026-12-31")
        self.assertEqual(TaskStore(self.db).list()[0]["due_date"], "2026-12-31")

    def test_list_filters_by_status(self):
        first = self.store.add("a")
        second = self.store.add("b")
        self.store.set_status(second["id"], "done")

        self.assertEqual([task["id"] for task in self.store.list("todo")], [first["id"]])
        self.assertEqual([task["id"] for task in self.store.list("done")], [second["id"]])
        self.assertEqual(len(self.store.list()), 2)

    def test_stats_counts(self):
        self.store.add("a")
        self.store.add("b")
        self.store.set_status(self.store.add("c")["id"], "doing")

        stats = self.store.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["todo"], 2)
        self.assertEqual(stats["doing"], 1)
        self.assertEqual(stats["done"], 0)

    def test_persistence_across_instances(self):
        self.store.add("survive me")
        self.assertEqual(len(TaskStore(self.db).list()), 1)

    def test_validation(self):
        with self.assertRaises(StoreError):
            self.store.add("   ")
        with self.assertRaises(StoreError):
            self.store.add("x", priority="urgent")
        with self.assertRaises(StoreError):
            self.store.set_status("nope", "done")

        for bad_due_date in ("2026/12/31", "2026-13-01", "not-a-date", "", 20261231):
            with self.assertRaises(StoreError):
                self.store.add("dated", due_date=bad_due_date)

    def test_delete_removes_task(self):
        task = self.store.add("temporary")
        removed = self.store.delete(task["id"])

        self.assertEqual(removed, task)
        self.assertEqual(self.store.list(), [])
        self.assertEqual(TaskStore(self.db).list(), [])

    def test_delete_missing_raises(self):
        retained = self.store.add("retain me")

        with self.assertRaisesRegex(StoreError, r"no task with id 'nope'"):
            self.store.delete("nope")

        remaining = TaskStore(self.db).list()
        self.assertEqual([task["id"] for task in remaining], [retained["id"]])

    def test_corrupt_file(self):
        self.db.write_text("{not a list", encoding="utf-8")
        with self.assertRaises(StoreError):
            TaskStore(self.db).list()

    def test_empty_file(self):
        self.db.write_text("[]", encoding="utf-8")
        self.assertEqual(TaskStore(self.db).list(), [])


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "tasks.json"
        self.previous_data_file = os.environ.get("TASKER_DATA_FILE")
        os.environ["TASKER_DATA_FILE"] = str(self.db)

    def tearDown(self):
        if self.previous_data_file is None:
            os.environ.pop("TASKER_DATA_FILE", None)
        else:
            os.environ["TASKER_DATA_FILE"] = self.previous_data_file
        self.tmp.cleanup()

    def run_cli(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            return_code = cli_mod.main(argv)
        return return_code, stdout.getvalue(), stderr.getvalue()


class TaskCliDeleteTests(CliTestCase):
    def test_delete_command(self):
        return_code, stdout, stderr = self.run_cli(["add", "delete me"])
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr, "")
        task_id = stdout.split()[1]

        return_code, stdout, stderr = self.run_cli(["delete", task_id])
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn(f"deleted {task_id}", stdout)

        return_code, stdout, stderr = self.run_cli(["list"])
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("(no tasks)", stdout)

    def test_delete_unknown_id_returns_error(self):
        return_code, stdout, stderr = self.run_cli(["delete", "zzz"])

        self.assertEqual(return_code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("error:", stderr)
        self.assertIn("no task with id 'zzz'", stderr)


if __name__ == "__main__":
    unittest.main()
