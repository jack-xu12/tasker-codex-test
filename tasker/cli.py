"""Command line interface for Tasker. A thin wrapper over tasker.store."""
from __future__ import annotations

import argparse
import json
import sys

from .store import VALID_PRIORITIES, VALID_STATUS, StoreError, TaskStore


def _print_tasks(tasks: list[dict]) -> None:
    if not tasks:
        print("(no tasks)")
        return
    for t in tasks:
        due = f" (due {t['due_date']})" if t.get("due_date") else ""
        print(f"{t['id']}  [{t['status']:<5}] ({t['priority']:<6}) {t['title']}{due}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tasker", description="Tiny task manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a task")
    a.add_argument("title")
    a.add_argument("--priority", choices=VALID_PRIORITIES, default="normal")
    a.add_argument("--due", dest="due_date", help="due date in YYYY-MM-DD format")

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("--status", choices=VALID_STATUS)

    done = sub.add_parser("done", help="mark a task done")
    done.add_argument("id")

    delete = sub.add_parser("delete", help="delete a task")
    delete.add_argument("id")

    sub.add_parser("stats", help="show statistics")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = TaskStore()
    try:
        if args.cmd == "add":
            t = store.add(args.title, args.priority, args.due_date)
            print(f"added {t['id']}")
        elif args.cmd == "list":
            _print_tasks(store.list(args.status))
        elif args.cmd == "done":
            t = store.set_status(args.id, "done")
            print(f"done {t['id']}: {t['title']}")
        elif args.cmd == "delete":
            t = store.delete(args.id)
            print(f"deleted {t['id']}: {t['title']}")
        elif args.cmd == "stats":
            print(json.dumps(store.stats(), ensure_ascii=False))
    except StoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())