# BTC Grid Decision Engine

> **Living document**: aktualizuj po każdej zmianie architektury, nowym pattern lub bug fixie.

---

## Purpose

Decision-support system dla grid tradingu BTC (spot, Bybit). Odpowiada na pytanie: "Jeśli chcę uruchomić grid TERAZ, gdzie najbliższy BUY, gdzie SELL, jak szeroki grid i czy w ogóle warto?". System NIE składa zleceń, tylko rekomenduje.

**Status: Phase 1 zakończona (2026-08-13), werdykt GO** (raport: `raport-phase1.md`). Dokument wiążący: `plan-v2.md`. `plan-v1.md` = archiwum researchu. Dane 24 mies. 1m (Binance + Bybit) pobrane, kalibracja percentyli potwierdzona walk-forwardowo (odchylenia <2 pp). Następne: Phase 3 silniki + Phase 4 backtest + Phase 5 dashboard.

**Ważne techniczne:** `python` w PATH wskazuje na venv Hermesa BEZ pip; zawsze używać pełnej ścieżki `C:/Users/tommi/AppData/Local/Programs/Python/Python311/python.exe`. Oscillation Score = percentyl efficiency ratio vs 90 dni (surowa formuła net/path nie działa, patrz raport).

**Nowe w V2:** Oscillation Score (0-100, falowanie vs przesunięcie netto), warianty Conservative/Balanced/Aggressive (P70/P60/P50), drabinka z mnożnikami 1.0/1.75/2.75/4.0, reguły przeliczania rekomendacji, samoocena (JSONL log + dzienny skrypt). Horyzonty ekskursji przycięte do 1h/4h/24h. Wycięte: ADX, EMA-composite, macierz timeframe'ów, cross-checki Kraken/Coinbase, rolling optimizer spreadu (to V3).

## Kluczowe decyzje projektowe (z researchu 2026-08-13)

- **Silnik spacingu: empiryczne kwantyle ekskursji** (rozkład max ruchu w horyzoncie h), NIE goły ATR. ATR zostaje jako benchmark.
- **Ekskursje górne (U_h) i dolne (D_h) liczone OSOBNO**, nigdy jako max|move|.
- **Percentyl 60 = ~40% szansy dotknięcia** (P(M >= Q60) = 0.40). Nie mylić kierunku.
- **Trend: znormalizowany OLS slope log ceny + R² jako gate.** ADX odrzucony. Wpływ trendu na spacing MAŁY (BTC 1-4h wykazuje mean reversion, nie momentum).
- **Dane: Binance Vision 1m ZIP (historia) + Bybit V5 (live)**, nigdy nie mieszać venue w jednej serii. TradingView odpada (brak API, ToS).
- **Fees Bybit spot: 0.1%/0.1%**, round-trip break-even ~0.2002% gross. Minimum Profitable Distance ~0.28-0.30%.
- **Backtest: własny event-driven engine na 1m barach**, 3 tryby fill (optimistic/base/stress), walk-forward.
- **Dashboard MVP: single-file HTML, DYNAMICZNY** (wymóg Toma 2026-08-13): żywa warstwa w JS dociąga cenę + ostatnie 24-48h świec z publicznego API przy każdym otwarciu i liczy rekomendację dla ceny z tej minuty. Python tylko odświeża tabele kwantyli raz dziennie (rolling 60-90 dni). Historia 2 lat wyłącznie do walidacji/backtestu, nie do codziennej pracy. CORS Bybit do sprawdzenia w Phase 2 (fallback: Binance w warstwie żywej).

## Tech Stack (planowany)

Python 3.11, pandas/numpy, requests (Bybit REST), Parquet + DuckDB, Chart.js single-file HTML dashboard.

## Active Files

| File | Purpose |
|------|---------|
| `plan-v1.md` | Pełny research + plan techniczny (15 sekcji), zatwierdzany przez Toma |
| `CLAUDE.md` | Ten plik |

## Konwencje

- Wszystkie dokumenty po polsku
- Bez em dashy w plikach i outputach
- Waluty: USD/USDT, format `$65 000` lub `65 000 USDT`
- Konto docelowe: Bybit spot (Tom ma tam konto, dane w `02-Projects/BTC/crypto-tracker/data/bybit/`)

## Self-Update Rule

Update po każdej fazie implementacji, zmianie decyzji projektowej lub odkryciu ograniczenia API.
