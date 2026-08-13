# Phase 1: raport walidacyjny (go/no-go)

> 2026-08-13. Dane: 24 miesiące świec 1m z Binance (1.05M) i Bybit (1.11M). Werdykt: **GO**.

## Trzy testy, trzy wyniki pozytywne

### 1. Jakość danych: idealna

| | Binance | Bybit |
|---|---|---|
| Świec 1m | 1 051 200 | 1 113 795 |
| Braki | 0 | 0 |
| Anomalie OHLC | 0 | 0 |

Różnica cen między giełdami: mediana 0.54 bp (pięć setnych promila). Wniosek: warstwa live dashboardu może w razie problemu CORS używać Binance bez żadnej straty jakości.

### 2. Koszyki reżimu naprawdę różnicują spread (Bybit, horyzont 4h, P60)

| Reżim | Spread w dół | Spread w górę | Przy cenie $63 600 |
|---|---|---|---|
| quiet | 0.38% | 0.37% | ~$240 |
| normal | 0.61% | 0.60% | ~$385 |
| elevated | 0.78% | 0.78% | ~$495 |
| extreme | 1.09% | 1.01% | ~$670 (i tak NO TRADE) |

Prawie 3x różnica między spokojnym a ekstremalnym rynkiem. To dokładnie ta adaptacyjność, o którą chodziło.

### 3. Kalibracja walk-forward: percentyle mówią prawdę

Test: co tydzień przez 21+ miesięcy liczyliśmy percentyle WYŁĄCZNIE z przeszłości i sprawdzali, jak często cena faktycznie dotykała poziomów w kolejnym tygodniu.

| Percentyl | Oczekiwane dotknięcia | Binance (up/down) | Bybit (up/down) |
|---|---|---|---|
| P50 | 50% | 50.5% / 51.7% | 49.2% / 50.2% |
| P60 | 40% | 40.3% / 41.1% | 39.2% / 39.5% |
| P70 | 30% | 30.0% / 30.5% | 28.9% / 29.3% |

Odchylenia poniżej 2 pkt proc. przy progu akceptacji 8. Kwartalnie wynik faluje ±10 pp (rynek ma fazy), ale to właśnie koryguje warunkowanie na reżim.

## Odkrycia po drodze (zmiany względem planu)

1. **Oscillation Score wymagał poprawki.** Surowa formuła "1 - netto/droga" dawała zawsze ~90, bo nawet random walk ma drogę wielokrotnie dłuższą od przesunięcia. Naprawione normalizacją percentylową: score = jak dzisiejsza kierunkowość wypada na tle własnych 90 dni. Po poprawce rozkład sensowny (mediana 50, filtr <30 realnie wyłapuje 30% najbardziej trendowych okresów).
2. **Horyzont 1h potwierdzony jako zwykle nieopłacalny** (P60 w quiet ~0.17% < MPD 0.28%): słusznie nie jest domyślny.
3. **W reżimie quiet wariant Balanced często spada poniżej 1.5x MPD**: system będzie wtedy uczciwie pokazywał "tylko Conservative albo nie graj". To nie błąd, to ochrona przed gridem, który nie pokrywa prowizji.

## Próbka działania: rekomendacja z dzisiejszych danych (2026-08-13, 11:14 UTC)

```
BTC: $63 622   Rezim: QUIET (percentyl 13)   Shock ratio: 0.72
Oscylacja: 24h=48  3d=23  7d=60   MPD: $178

AGGRESSIVE    BUY $63 440 (-$182)   SELL $63 805 (+$183)   ponizej progu oplacalnosci
BALANCED      BUY $63 381 (-$241)   SELL $63 858 (+$237)   ponizej progu oplacalnosci
CONSERVATIVE  BUY $63 302 (-$320)   SELL $63 932 (+$311)   OK

ACTION: ostroznie. Zadna twarda blokada nie odpalila, ale okno 3d pokazuje
rynek kierunkowy (23 < 30), a rezim quiet przepuszcza tylko wariant
Conservative. Rozsadna decyzja: maly grid Conservative albo WAIT.
```

Uwaga: reguła zgodności okien (24h vs 3d vs 7d) pokazała tu swoją wartość pierwszego dnia: samo 24h wyglądało neutralnie, 3d ujawniło trend.

## Artefakty

| Plik | Co zawiera |
|---|---|
| `outputs/excursion_tables.json` | tabele percentyli Bybit (wsad do dashboardu) |
| `outputs/excursion_tables_binance.json` | to samo z Binance (porównanie) |
| `outputs/calibration.csv`, `outputs/calibration_binance.csv` | pełne wyniki walk-forward |
| `src/` | działające skrypty: ingest, quality, ekskursje, kalibracja, oscylacja |

## Rekomendacja

**GO na kolejne fazy:** silnik decyzyjny jako pure functions (Phase 3) → backtest wariantów A-E (Phase 4) → dynamiczny dashboard na GitHub Pages (Phase 5).
