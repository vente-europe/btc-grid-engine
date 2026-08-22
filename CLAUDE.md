# BTC Grid Decision Engine

> **Living document**: aktualizuj po każdej zmianie architektury, nowym pattern lub bug fixie.

---

## Purpose

Decision-support system dla grid tradingu BTC (spot, Bybit). Odpowiada na pytanie: "Jeśli chcę uruchomić grid TERAZ, gdzie najbliższy BUY, gdzie SELL, jak szeroki grid i czy w ogóle warto?". System NIE składa zleceń, tylko rekomenduje.

**Status: dashboard V1 LIVE (2026-08-13):** https://vente-europe.github.io/btc-grid-engine/ (repo `vente-europe/btc-grid-engine`, lokalny branch `master`, push `master:main`). Phase 1 walidacja: GO (`raport-phase1.md`, kalibracja walk-forward <2 pp). Logika decyzyjna w JS w `src/dashboard/template.html` (live fetch Bybit, fallback Binance; CORS potwierdzony na obu). Kalibracja dzienna: Task Scheduler "BTC Grid Calibrate" 06:30 → `calibrate-daily.bat` → `src/calibrate.py` + `src/push_pages.py` (token z workspace-root `.env`). Eventy FOMC/CPI: `config/events.json` (Fed + BLS, zweryfikowane 2026-08-13). **Następne: Phase 4 backtest wariantów A-E + samoocena (log rekomendacji).**

**Fix Task Scheduler (2026-08-22):** zadanie "BTC Grid Calibrate" było zarejestrowane z NIEZACYTOWANĄ ścieżką (Command=`c:\AI`, reszta w Arguments) i od 2026-08-13 nigdy się nie wykonało (kalibracja stała 9 dni, brak calibrate.log). Przerejestrowane z pełną cytowaną ścieżką do calibrate-daily.bat + wyłączone DisallowStartIfOnBatteries/StopIfGoingOnBatteries + włączone StartWhenAvailable (laptop). Lekcja: przy schtasks zawsze weryfikować `schtasks /query /tn X /xml` po rejestracji, sam "SUCCESS" nie wystarczy.

**Zakładki (2026-08-22):** dashboard ma 2 zakładki: "Silnik grid" (dotychczasowa zawartość) + "Backtest rebalansu" - symulacja constant-mix BTC/USDC (domyślnie 80/20) na historii Binance 1h (paginacja startTime, ~18 requestów na 2 lata, fallback Bybit V5 z paginacją wstecz przez end). Trigger: pasmo odchylenia udziału USDC w pkt proc. (wybór Toma; tryb cenowy odrzucony - matematycznie równoważny, opis w karcie pomocy). Egzekucja na zamknięciu świecy, prowizja od obrotu, rebalans przywraca dokładnie cel po prowizji (SELL S=(ct·V-cash)/(1-f+ct·f), BUY S=(cash-ct·V)/(1-ct·f)). Interwały 1h/4h/1d (downsampling po czasie zamknięcia kubełka UTC), okresy 183/365/730 dni, sweep progów 0.25-10pp, benchmarki: HODL 100% BTC i 80/20 bez rebalansu. Wykres dwupanelowy na wspólnej osi czasu: góra cena BTC + markery BUY/SELL, dół wartość portfela vs HODL (wymóg Toma 2026-08-22: sama krzywa kapitału była nieczytelna, oś do $200k przy 2x wzroście ceny wyglądała jak cena BTC). Stan w localStorage (klucze `gt`, `bt_*`). Testy sanity: `simRebalance`/`downsample` da się wyciągnąć regexem i przetestować w Node (funkcje czyste, bez DOM).

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
