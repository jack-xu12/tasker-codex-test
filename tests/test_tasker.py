import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tasker.store import StoreError, TaskStore  # noqa: E402


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "tasks.json"
        self.store = TaskStore(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_assigns_id_and_defaults(self):
        t = self.store.add("write docs")
        self.assertEqual(t["title"], "write docs")
        self.assertEqual(t["status"], "todo")
        self.assertEqual(t["priority"], "normal")
        self.assertIsNone(t["due_date"])
        self.assertEqual(len(t["id"]), 8)

    def test_add_stores_due_date(self):
        t = self.store.add("ship feature", due_date="2026-12-31")
        self.assertEqual(t["due_date"], "2026-12-31")
        self.assertEqual(TaskStore(self.db).list()[0]["due_date"], "2026-12-31")

    def test_list_filters_by_status(self):
        a = self.store.add("a")
        b = self.store.add("b")
        self.store.set_status(b["id"], "done")
        self.assertEqual([t["id"] for t in self.store.list("todo")], [a["id"]])
        self.assertEqual([t["id"] for t in self.store.list("done")], [b["id"]])
        self.assertEqual(len(self.store.list()), 2)

    def test_stats_counts(self):
        self.store.add("a")
        self.store.add("b")
        self.store.set_status(self.store.add("c")["id"], "doing")
        s = self.store.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["todo"], 2)
        self.assertEqual(s["doing"], 1)
        self.assertEqual(s["done"], 0)

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

    def test_corrupt_file(self):
        self.db.write_text("{not a list", encoding="utf-8")
        with self.assertRaises(StoreError):
            TaskStore(self.db).list()


if __name__ == "__main__":
    unittest.main()