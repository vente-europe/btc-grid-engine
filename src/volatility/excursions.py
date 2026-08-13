"""Serce systemu: rozklady maksymalnych ekskursji ceny w horyzoncie h.

Dla kazdej minuty t liczymy (na danych 1m):
  U_h(t) = max(High[t+1 .. t+h]) / Close[t] - 1     (ekskursja w gore)
  D_h(t) = 1 - min(Low[t+1 .. t+h]) / Close[t]      (ekskursja w dol)

Wynik: tabele percentyli per horyzont i per koszyk rezimu zmiennosci.
Zero lookahead: rezim w t liczony wylacznie z danych do t.
"""
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]

HORIZONS_H = [1, 4, 24]
PERCENTILES = [50, 60, 70, 80, 90]
REGIME_BOUNDS = {"quiet": (0, 25), "normal": (25, 75), "elevated": (75, 90), "extreme": (90, 100)}


def load_1m(venue: str = "bybit") -> pd.DataFrame:
    files = sorted((PROJECT / "data" / "parquet" / venue / "BTCUSDT" / "1m").glob("*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.sort_values("ts").drop_duplicates("ts").set_index("ts")
    # przerwy uzupelniamy ffill close (potrzebna ciagla siatka do rolling)
    full = df.resample("1min").agg({"open": "first", "high": "max", "low": "min",
                                    "close": "last", "volume": "sum"})
    full["close"] = full["close"].ffill()
    for col in ("open", "high", "low"):
        full[col] = full[col].fillna(full["close"])
    return full


def forward_excursions(df: pd.DataFrame, h_hours: int) -> pd.DataFrame:
    """Ekskursje forward w oknie h godzin (bez biezacej minuty)."""
    n = h_hours * 60
    # rolling max/min na odwroconej serii = forward-looking window
    fwd_high = df["high"][::-1].rolling(n, min_periods=n).max()[::-1].shift(-1)
    fwd_low = df["low"][::-1].rolling(n, min_periods=n).min()[::-1].shift(-1)
    up = fwd_high / df["close"] - 1.0
    down = 1.0 - fwd_low / df["close"]
    return pd.DataFrame({"up": up, "down": down})


def realized_vol_4h(df: pd.DataFrame) -> pd.Series:
    """RV z 5m log-returns w oknie 4h (per-hour, annualizacja zbedna)."""
    c5 = df["close"].resample("5min").last().ffill()
    r = np.log(c5 / c5.shift(1))
    rv = (r ** 2).rolling(48, min_periods=40).sum() / 4.0  # 48 x 5m = 4h -> per hour
    return np.sqrt(rv)


def vol_percentile(rv: pd.Series, baseline_days: int = 90) -> pd.Series:
    """Percentyl biezacej RV vs trailing baseline (bez lookahead)."""
    win = baseline_days * 24 * 12  # obserwacje 5-minutowe
    return rv.rolling(win, min_periods=win // 3).rank(pct=True) * 100


def regime_label(pct: float) -> str:
    for name, (lo, hi) in REGIME_BOUNDS.items():
        if lo <= pct < hi or (name == "extreme" and pct >= 90):
            return name
    return "normal"


def build_tables(venue: str = "bybit") -> dict:
    df = load_1m(venue)
    rv = realized_vol_4h(df)
    pct = vol_percentile(rv).reindex(df.index).ffill()
    regimes = pct.dropna().apply(regime_label)

    tables: dict = {}
    for h in HORIZONS_H:
        exc = forward_excursions(df, h)
        exc = exc.join(regimes.rename("regime")).dropna()
        # probkujemy co 15 min zeby zredukowac autokorelacje nakladajacych sie okien
        exc = exc[exc.index.minute % 15 == 0]
        tables[h] = {}
        for reg in list(REGIME_BOUNDS) + ["all"]:
            sub = exc if reg == "all" else exc[exc["regime"] == reg]
            if len(sub) < 200:
                continue
            tables[h][reg] = {
                "n": len(sub),
                "up": {p: float(np.percentile(sub["up"], p)) for p in PERCENTILES},
                "down": {p: float(np.percentile(sub["down"], p)) for p in PERCENTILES},
            }
    return tables


if __name__ == "__main__":
    import json
    tables = build_tables()
    out = PROJECT / "outputs" / "excursion_tables.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(tables, indent=2))
    print(f"Zapisano {out}")
    for h, regs in tables.items():
        print(f"\n=== horyzont {h}h ===")
        for reg, t in regs.items():
            u60, d60 = t["up"][60] * 100, t["down"][60] * 100
            print(f"  {reg:9s} n={t['n']:7,}  P60 up={u60:.3f}%  down={d60:.3f}%")
