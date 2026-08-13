"""Oscillation Score: czy rynek faluje (dobrze dla grida), czy jedzie (zle).

Wersja 2 (2026-08-13). Surowa formula 1 - net/path NIE dziala: na N swiecach
nawet random walk daje net/path ~ sqrt(2/(pi*N)), wiec score byl zawsze ~90.

Poprawka: liczymy efficiency ratio ER = |przesuniecie netto| / droga,
a score to percentyl ER wzgledem wlasnej 90-dniowej historii, odwrocony:
  score 100 = rynek faluje bardziej niz zwykle (idealny grid)
  score 0   = rynek jedzie kierunkowo mocniej niz zwykle (nie graj)
Prog no-trade <30 oznacza: ER w gornych 30% najbardziej trendowych okresow.
"""
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
BASELINE_DAYS = 90


def efficiency_ratio(close_15m: pd.Series, window_hours: int) -> pd.Series:
    n = window_hours * 4  # swiece 15m
    net = (close_15m - close_15m.shift(n)).abs()
    path = close_15m.diff().abs().rolling(n, min_periods=n).sum()
    return net / path.replace(0, pd.NA)


def oscillation_score(close_15m: pd.Series, window_hours: int = 24,
                      baseline_days: int = BASELINE_DAYS) -> pd.Series:
    er = efficiency_ratio(close_15m, window_hours)
    base = baseline_days * 24 * 4  # obserwacje 15m
    pct = er.rolling(base, min_periods=base // 3).rank(pct=True)
    return ((1 - pct) * 100).clip(0, 100)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT / "src" / "volatility"))
    from excursions import load_1m

    df = load_1m("binance")
    c15 = df["close"].resample("15min").last().ffill()
    for w in (24, 72, 168):
        s = oscillation_score(c15, w).dropna()
        print(f"okno {w:>3}h: mediana={s.median():.0f}  <30 przez {(s < 30).mean()*100:.0f}% "
              f"czasu  >70 przez {(s > 70).mean()*100:.0f}% czasu")
