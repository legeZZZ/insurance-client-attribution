"""M2: public external-event timeline ingestion + mapping coverage stats.

Line B previously required external events to be hand-registered. This module
ships a curated timeline of public macro/regulatory events (sample data, all
from public announcements) and measures how well detected anomalies map onto
it — the 'mapping coverage' metric:

  coverage = detected anomalies with a timeline event within ±max_lag days
             / all detected anomalies

Unmapped anomalies stay UNEXPLAINED (honest bucket); unused timeline events
are reported separately (they may have had no measurable footprint).

Reproduce: python3 -m attribution.external_events
Output:    outputs/external_event_mapping.json
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .baseline_attribution import attribute_baseline

DAY0 = date(2024, 6, 1)

# Curated sample: public events possibly relevant to insurance/mutual-aid
# style CTR & premium panels. Dates from public announcements; kept as
# demonstration data, not a production feed.
PUBLIC_EVENT_TIMELINE: list[dict[str, Any]] = [
    {
        "event_id": "promo_618_2024",
        "date": "2024-06-18",
        "kind": "seasonality",
        "desc": "618 电商大促分流用户注意力（公开日历事件）",
    },
    {
        "event_id": "lpr_2024_07",
        "date": "2024-07-22",
        "kind": "macro_rate",
        "desc": "LPR 一年期/五年期各下调 10bp（公开发布）",
    },
    {
        "event_id": "reg_baoxing_heyi",
        "date": "2024-08-02",
        "kind": "regulation",
        "desc": "银保渠道费用规范持续执行（报行合一，公开政策）",
    },
    {
        "event_id": "school_season_2024_09",
        "date": "2024-09-01",
        "kind": "seasonality",
        "desc": "开学季（周期性公开日历事件）",
    },
]


def _day_index(iso: str) -> int:
    y, m, d = (int(x) for x in iso.split("-"))
    return (date(y, m, d) - DAY0).days


def map_anomalies_to_events(
    alerts: Sequence[Mapping[str, Any]],
    timeline: Sequence[Mapping[str, Any]] | None = None,
    max_lag_days: int = 7,
) -> dict[str, Any]:
    """Greedy lag-constrained matching between detected step days and events."""
    timeline = timeline if timeline is not None else PUBLIC_EVENT_TIMELINE
    events = [{**ev, "day": _day_index(ev["date"])} for ev in timeline]
    used: set = set()
    mapped, unmapped = [], []
    for alert in alerts:
        onset = alert["onset_day"]
        best, best_lag = None, max_lag_days + 1
        for ev in events:
            if ev["event_id"] in used:
                continue
            lag = abs(onset - ev["day"])
            if lag <= max_lag_days and lag < best_lag:
                best, best_lag = ev, lag
        if best is None:
            unmapped.append(dict(alert))
        else:
            used.add(best["event_id"])
            mapped.append(
                {
                    "onset_day": onset,
                    "event_id": best["event_id"],
                    "kind": best["kind"],
                    "desc": best["desc"],
                    "lag_days": best_lag,
                    "claim_type": "TEMPORAL_ASSOCIATION",
                    "note": "时间对齐的外生事件线索；不作因果断言。",
                }
            )
    total = len(alerts)
    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "unused_events": [
            ev["event_id"] for ev in events if ev["event_id"] not in used
        ],
        "coverage": {
            "detected_anomalies": total,
            "mapped": len(mapped),
            "mapping_coverage": round(len(mapped) / total, 4) if total else None,
            "timeline_utilization": round(len(used) / len(events), 4)
            if events
            else None,
            "unmapped_policy": "未映射异常保持 UNEXPLAINED，不强行挂靠事件。",
        },
    }


def _simulate_panel(seed: int = 20260811) -> dict[str, Any]:
    """90-day panel: two public events lift/press the metric, plus one
    unregistered product change. Ground truth noted for verification."""
    rng = np.random.default_rng(seed)
    days = np.arange(90)
    control = 500 + 0.3 * days + rng.normal(0, 6, 90)  # baseline trend
    gap = rng.normal(0, 4, 90)
    truth = {"events": [], "unregistered_change_day": None}
    # Public events with negative short-term footprint (step detector is
    # one-sided on sustained downward shifts):
    promo_day = _day_index("2024-06-18")  # day 17
    reg_day = _day_index("2024-08-02")  # day 62
    gap[promo_day : promo_day + 7] -= 30.0  # 618 attention diversion (temporary)
    gap[reg_day:] -= 35.0  # fee regulation -> channel squeeze
    truth["events"] = [
        {"event_id": "promo_618_2024", "day": promo_day},
        {"event_id": "reg_baoxing_heyi", "day": reg_day},
    ]
    unreg_day = 40
    gap[unreg_day:] -= 30.0  # unregistered product change
    truth["unregistered_change_day"] = unreg_day
    treated = control + gap
    return {
        "days": days.tolist(),
        "control": control.tolist(),
        "treated": treated.tolist(),
        "truth": truth,
    }


def main() -> None:
    panel = _simulate_panel()
    # Run Line B with NO hand-registered external events: detection only.
    result = attribute_baseline(
        days=panel["days"],
        control=panel["control"],
        treated=panel["treated"],
        change_registry=[],
        external_registry=[],
        experiments={},
        detection_threshold=12.0,
    )
    mapping = map_anomalies_to_events(result["unregistered_alerts"])
    truth = panel["truth"]
    mapped_ids = {m["event_id"] for m in mapping["mapped"]}
    truth_event_ids = {e["event_id"] for e in truth["events"]}
    out = {
        "scenario": "90-day panel, 2 public events + 1 unregistered change (synthetic)",
        "detected_alerts": result["unregistered_alerts"],
        "timeline": PUBLIC_EVENT_TIMELINE,
        "mapping": mapping,
        "verification": {
            "truth_events_recalled": sorted(mapped_ids & truth_event_ids),
            "truth_events_total": sorted(truth_event_ids),
            "unregistered_change_correctly_unmapped": any(
                abs(a["onset_day"] - truth["unregistered_change_day"]) <= 5
                for a in mapping["unmapped"]
            ),
            "note": "未注册产品变动不应挂靠任何公开事件——保持 UNEXPLAINED 为正确行为。",
        },
    }
    out_path = (
        Path(__file__).resolve().parent.parent
        / "outputs"
        / "external_event_mapping.json"
    )
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["mapping"]["coverage"], ensure_ascii=False, indent=2))
    print(json.dumps(out["verification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
