"""Generate a synthetic catalyst_training-shaped CSV for demos and tests.

Mirrors the real export's columns but contains NO real data. A mild edge is
embedded for confirmed, high-confidence catalysts so the demo shows the oracle
finding (and gating) a signal. Deterministic.

    python scripts/make_sample_catalysts.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta

OUT = "examples/data/catalyst_sample.csv"
COLS = [
    "id", "symbol", "headline", "summary", "catalyst_type", "positive", "confirmed",
    "confidence", "reason", "trade_result", "pnl_pct", "created_at",
    "premarket_gap_pct", "pre_open_pct", "midday_pct", "eod_pct", "detection_price",
    "premarket_checked_at", "eod_checked_at", "features",
]
TYPES = ["EARNINGS", "CONTRACT", "ANALYST_UPGRADE", "CLINICAL_TRIAL", "MA", "OTHER"]
SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]


def main() -> None:
    rng = random.Random(11)
    start = datetime(2026, 1, 2, 14, 0, 0)
    rows = []
    for i in range(200):
        confirmed = rng.random() < 0.4
        confidence = rng.choice([0, 20, 40, 55, 60, 70, 85, 95])
        positive = confidence >= 40 and rng.random() < 0.8
        ctype = rng.choice(TYPES)
        # Embedded edge: confirmed AND confidence>=60 has a positive mean move.
        edge = 1.4 if (confirmed and confidence >= 60) else 0.0
        eod = rng.gauss(edge, 4.0)
        detection_price = round(rng.uniform(3, 200), 2)
        ts = start + timedelta(hours=i * 7)
        feats = {
            "rsi": round(rng.uniform(20, 80), 1),
            "rvol": round(rng.uniform(0.5, 6), 2),
            "gap_pct": round(rng.gauss(0, 3), 2),
            "spy_regime": 1,
        }
        rows.append({
            "id": f"{i:08d}", "symbol": rng.choice(SYMS),
            "headline": f"Synthetic {ctype} headline #{i}", "summary": "",
            "catalyst_type": ctype, "positive": str(positive).lower(),
            "confirmed": str(confirmed).lower(), "confidence": confidence,
            "reason": "" if positive else "blocked: low confidence",
            "trade_result": "", "pnl_pct": "",
            "created_at": ts.strftime("%Y-%m-%d %H:%M:%S+00"),
            "premarket_gap_pct": round(rng.gauss(0, 2), 2),
            "pre_open_pct": round(rng.gauss(0, 1.5), 2),
            "midday_pct": round(eod * rng.uniform(0.4, 0.9), 2),
            "eod_pct": round(eod, 2), "detection_price": detection_price,
            "premarket_checked_at": "", "eod_checked_at": "",
            "features": json.dumps(feats),
        })
    import os
    os.makedirs("examples/data", exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
