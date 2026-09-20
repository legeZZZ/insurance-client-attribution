"""Application-owned resident scan process. Stop with job stop or SIGTERM."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.scan_service import ScanService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-ticks", type=int)
    args = parser.parse_args()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    service = ScanService(args.db)
    try:
        count = 0
        while running:
            status = service.status(args.job)
            if not status["enabled"]:
                break
            try:
                result = service.tick(args.job, force=args.once)
                print(
                    json.dumps(
                        {"job": args.job, "status": result["status"]},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                service._event(
                    "SCAN_INPUT_FAILED", {"job": args.job, "error": str(exc)}
                )
            count += 1
            if args.once or (args.max_ticks is not None and count >= args.max_ticks):
                break
            time.sleep(min(1.0, status["config"]["interval_seconds"]))
    finally:
        service.close()


if __name__ == "__main__":
    main()
