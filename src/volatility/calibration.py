"""Kalibracja walk-forward: czy P60 z historii naprawde oznacza ~40% dotkniec?

Metoda: idziemy po historii co tydzien. W kazdym punkcie:
  1. liczymy percentyle ekskursji WYLACZNIE z poprzednich 90 dni (bez lookahead)
  2. przez nastepny tydzien sprawdzamy co 4h: czy poziom BUY/SELL wyznaczony
     z tych percentyli zostal dotkniety w horyzoncie h
  3. porownujemy czestosc dotkniec z oczekiwana (1 - percentyl)

Werdykt go/no-go: dotkniecia w przedziale +/- 8 pkt proc. od oczekiwanych.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from excursions import load_1m, forward_excursions  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]

HORIZON_H = 4
TAUS = [50, 60, 70]
LOOKBACK_DAYS = 90
STEP_HOURS = 4          # co ile sprawdzamy nowy punkt startowy
REFIT_DAYS = 7          # co ile przeliczamy percentyle


def run(venue: str = "bybit") -> pd.DataFrame:
    df = load_1m(venue)
    exc = forward_excursions(df, HORIZON_H)  # forward: uzywane TYLKO do oceny wyniku
    idx = df.index

    start = idx.min() + pd.Timedelta(days=LOOKBACK_DAYS)
    refit_points = pd.date_range(start, idx.max() - pd.Timedelta(days=REFIT_DAYS), freq=f"{REFIT_DAYS}D")

    rows = []
    for t0 in refit_points:
        hist = exc.loc[t0 - pd.Timedelta(days=LOOKBACK_DAYS): t0]
        hist = hist[hist.index.minute % 15 == 0].dropna()
        if len(hist) < 500:
            continue
        q = {tau: {"up": np.percentile(hist["up"], tau),
                   "down": np.percentile(hist["down"], tau)} for tau in TAUS}

        test = exc.loc[t0: t0 + pd.Timedelta(days=REFIT_DAYS)].dropna()
        test = test[test.index.hour % STEP_HOURS == 0]
        test = test[test.index.minute == 0]
        if test.empty:
            continue
        for tau in TAUS:
            rows.append({
                "t0": t0, "tau": tau, "n": len(test),
                "touch_up": float((test["up"] >= q[tau]["up"]).mean()),
                "touch_down": float((test["down"] >= q[tau]["down"]).mean()),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    res = run()
    out = PROJECT / "outputs" / "calibration.csv"
    out.parent.mkdir(exist_ok=True)
    res.to_csv(out, index=False)
    print(f"Zapisano {out}  ({len(res)} wierszy, {res['t0'].nunique()} okien walk-forward)\n")
    print("=== KALIBRACJA (horyzont 4h, walk-forward tygodniowy) ===")
    print(f"{'tau':>4} {'oczekiwane':>11} {'up: srednia':>12} {'down: srednia':>14} {'werdykt':>10}")
    for tau in TAUS:
        sub = res[res["tau"] == tau]
        exp = (100 - tau) / 100
        up, dn = sub["touch_up"].mean(), sub["touch_down"].mean()
        ok = abs(up - exp) <= 0.08 and abs(dn - exp) <= 0.08
        print(f"{tau:>4} {exp:>10.0%} {up:>12.1%} {dn:>14.1%} {'OK' if ok else 'ODCHYLKA':>10}")
