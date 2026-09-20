#!/usr/bin/env python3
"""Build the offline snapshot for final-console-v3.html.

Runs every v2 console endpoint against the seeded workspace (all real
pipeline outputs), adds the B-line evidence candidates, and inlines the
result into web/static/final-console-v3.html by replacing the template
placeholder. Service mode ignores the inline snapshot and fetches live.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import console_v2  # noqa: E402

WORKDIR = PROJECT / "runtime_data" / "console_v2"
TEMPLATE = PROJECT / "web" / "static" / "final-console-v3.template.html"
OUTPUT = PROJECT / "web" / "static" / "final-console-v3.html"
BLINE = PROJECT / "runtime_data" / "evidence" / "T2-company-lineB.json"
PLACEHOLDER = "/*__V3_INLINE__*/null"


def build_snapshot() -> dict:
    if not (WORKDIR / "watchlist.json").is_file():
        raise SystemExit(
            "console_v2 workspace not seeded; run "
            ".venv/bin/python tools/seed_console_v2.py first")
    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "overview": console_v2.overview(WORKDIR),
        "factors": console_v2.factors(WORKDIR),
        "watchlist": console_v2.watchlist(WORKDIR),
        "alerts": console_v2.alerts(WORKDIR),
        "conflicts": console_v2.conflicts(WORKDIR),
        "skills": console_v2.list_skills(WORKDIR),
        "evidence": console_v2.evidence(WORKDIR),
        "ledger": console_v2.factor_ledger(WORKDIR),
        "queue": console_v2.feedback_queue(WORKDIR),
    }
    if BLINE.is_file():
        data = json.loads(BLINE.read_text(encoding="utf-8"))
        snapshot["bline_candidates"] = data.get("association_candidates", [])
    else:
        snapshot["bline_candidates"] = []
    return snapshot


def main() -> None:
    snapshot = build_snapshot()
    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise SystemExit(f"placeholder missing in {TEMPLATE}")
    inline = json.dumps(snapshot, ensure_ascii=False)
    html = html.replace(PLACEHOLDER, inline, 1)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"written: {OUTPUT} ({len(html.encode('utf-8'))} bytes, "
          f"{len(snapshot['bline_candidates'])} b-line candidates, "
          f"{len(snapshot['alerts']['alerts'])} alerts)")


if __name__ == "__main__":
    main()
