"""Dzienny job kalibracyjny: odswieza dane, liczy baseline'y, buduje index.html.

Kroki:
  1. dociagniecie swiezych swiec Bybit 1m (ostatnie ~95 dni, przyrostowo)
  2. tabele percentyli ekskursji per rezim (pelna historia, walidowane w Phase 1)
  3. baseline'y percentylowe z trailing 90 dni: RV 4h + efficiency ratio (24h/72h/168h)
  4. wstrzykniecie calibration JSON do template -> index.html

Uruchomienie: python src/calibrate.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src" / "volatility"))
sys.path.insert(0, str(PROJECT / "src" / "regime"))
sys.path.insert(0, str(PROJECT / "src" / "data"))

from excursions import build_tables, load_1m, realized_vol_4h  # noqa: E402
from oscillation import efficiency_ratio  # noqa: E402
from bybit_backfill import fetch_window  # noqa: E402


def update_recent(days: int = 95) -> None:
    """Dociaga ostatnie N dni z Bybit i merguje do miesiecznych parquetow."""
    out_dir = PROJECT / "data" / "parquet" / "bybit" / "BTCUSDT" / "1m"
    now = datetime.now(timezone.utc)
    start_ms = int((now.timestamp() - days * 86400) * 1000)
    end_ms = int(now.timestamp() * 1000)
    rows = fetch_window(start_ms, end_ms)
    df = pd.DataFrame(rows, columns=["ts_ms", "open", "high", "low", "close", "volume", "turnover"])
    df = df.astype({"ts_ms": "int64", "open": "float64", "high": "float64",
                    "low": "float64", "close": "float64", "volume": "float64"})
    df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df = df[["ts", "open", "high", "low", "close", "volume"]]
    for period, g in df.groupby(df["ts"].dt.strftime("%Y-%m")):
        p = out_dir / f"{period}.parquet"
        if p.exists():
            old = pd.read_parquet(p)
            g = pd.concat([old, g]).sort_values("ts").drop_duplicates("ts")
        g.to_parquet(p, index=False)
    print(f"update_recent: +{len(df):,} swiec do {df['ts'].max()}")


def build_baselines(df: pd.DataFrame, days: int = 90) -> dict:
    """Kwantyle (0..100) RV4h i ER z trailing N dni: lookup percentyla w JS."""
    cutoff = df.index.max() - pd.Timedelta(days=days)
    qgrid = list(range(101))

    rv = realized_vol_4h(df).loc[cutoff:].dropna()
    rv_q = np.percentile(rv, qgrid).tolist()

    c15 = df["close"].resample("15min").last().ffill()
    er_q = {}
    for w in (24, 72, 168):
        er = efficiency_ratio(c15, w).loc[cutoff:].dropna()
        er_q[str(w)] = np.percentile(er, qgrid).tolist()

    return {"rv4h_quantiles": rv_q, "er_quantiles": er_q, "baseline_days": days}


def main() -> None:
    try:
        update_recent()
    except Exception as e:  # noqa: BLE001
        print(f"UWAGA: update_recent nieudany ({e}), licze na istniejacych danych")

    df = load_1m("bybit")
    tables = build_tables("bybit")
    baselines = build_baselines(df)
    events = json.loads((PROJECT / "config" / "events.json").read_text(encoding="utf-8"))

    calibration = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "venue": "bybit",
        "symbol": "BTCUSDT",
        "last_candle_utc": df.index.max().isoformat(),
        "excursion_tables": tables,
        "baselines": baselines,
        "events": events["events"],
        "config": {
            "variants": {"aggressive": 50, "balanced": 60, "conservative": 70},
            "default_horizon": 4,
            "mpd_pct": 0.0028,
            "mpd_multiple_min": 1.5,
            "ladder_multipliers": [1.0, 1.75, 2.75, 4.0],
            "vol_percentile_max": 90,
            "shock_ratio_wait": 2.0,
            "oscillation_no_trade": 30,
            "oscillation_wait_3d": 30,
            "event_window_before_h": 2,
            "event_window_after_h": 2,
            "trend_z_block": 1.5,
            "trend_r2_gate": 0.3,
            "trend_shift_max": 0.25,
        },
    }

    out = PROJECT / "outputs" / "calibration.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(calibration), encoding="utf-8")
    print(f"Zapisano {out} ({out.stat().st_size/1024:.0f} KB)")

    template = (PROJECT / "src" / "dashboard" / "template.html").read_text(encoding="utf-8")
    html = template.replace("/*__CALIBRATION_JSON__*/null", json.dumps(calibration))
    (PROJECT / "index.html").write_text(html, encoding="utf-8")
    print(f"Zbudowano index.html ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
