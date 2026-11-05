"""Fail when a critical package drops below the minimum coverage (spec §14: 80%).

uv run pytest --cov=app --cov-report=json:coverage.json && uv run python scripts/coverage_gate.py
"""

import json
import sys
from pathlib import Path

MINIMUM = 80.0
PACKAGES = ("app/rules/", "app/matching/", "app/extraction/")


def main() -> int:
    files = json.loads(Path("coverage.json").read_text())["files"]
    failed = False
    for pkg in PACKAGES:
        statements = sum(
            v["summary"]["num_statements"] for k, v in files.items() if k.startswith(pkg)
        )
        covered = sum(v["summary"]["covered_lines"] for k, v in files.items() if k.startswith(pkg))
        pct = 100 * covered / statements if statements else 100.0
        ok = pct >= MINIMUM
        failed |= not ok
        print(f"{pkg:20} {pct:5.1f}%  {'ok' if ok else f'abaixo de {MINIMUM:.0f}%'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
