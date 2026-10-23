#!/usr/bin/env python3
"""Порог покрытия веток (CLAUDE.md §10.3): `app/*/model` и `app/auth` — не ниже 95 %.

Читает `coverage.json` (pytest --cov --cov-report=json). Считает взвешенно: строки + ветки.
"""

import json
import re
import sys
from pathlib import Path

THRESHOLD = 95.0
GROUPS = {
    "app/*/model": re.compile(r"^app/[a-z_]+/model/"),
    "app/auth": re.compile(r"^app/auth/"),
}


def main(path: str) -> int:
    files = json.loads(Path(path).read_text(encoding="utf-8"))["files"]
    failed = False
    for name, pattern in GROUPS.items():
        covered = total = 0
        for filename, data in files.items():
            if pattern.match(filename.replace("\\", "/")):
                summary = data["summary"]
                covered += summary["covered_lines"] + summary.get("covered_branches", 0)
                total += summary["num_statements"] + summary.get("num_branches", 0)
        percent = 100.0 * covered / total if total else 0.0
        verdict = "ok" if percent >= THRESHOLD else "НИЖЕ ПОРОГА"
        print(f"{name}: {percent:.1f} % (порог {THRESHOLD:.0f} %) — {verdict}")
        failed = failed or percent < THRESHOLD
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "backend/coverage.json"))
