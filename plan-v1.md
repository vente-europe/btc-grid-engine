# BTC Grid Decision Engine: research + plan techniczny V1

> Data: 2026-08-13. Research: 3 głębokie zapytania Perplexity (ok. 100 źródeł). Etap weryfikacji pomysłu pominięty na życzenie Toma; znane słabości ujęte wyłącznie jako ograniczenia projektowe, które system musi obsłużyć.
>
> Status: **do zatwierdzenia**. Żaden kod produkcyjny nie powstał.

---

## 1. Executive summary

Budujemy lokalny system decyzyjny (Python + dashboard), który dla bieżącej ceny BTC odpowiada: gdzie najbliższy BUY, gdzie SELL, jaka szerokość grida, czy w ogóle startować, z jaką pewnością.

Najważniejsze rozstrzygnięcia z researchu:

1. **Twoja intuicja percentylowa jest lepsza niż ATR.** Zamiast jednego wskaźnika zmienności system będzie estymował **empiryczny rozkład maksymalnych ekskursji ceny** w horyzoncie h (np. "jaki max ruch w górę / w dół zdarza się w ciągu 4h") i wybierał spacing jako kwantyl tego rozkładu. To dokładnie odpowiada pytaniu "jaki ruch jest osiągalny", czego ATR nie robi (ATR mierzy średni zakres świecy, bez interpretacji probabilistycznej, bez kierunku).
2. **Ekskursje w górę i w dół liczymy osobno.** Asymetria BUY/SELL wynika wtedy z danych, a nie z arbitralnej reguły.
3. **Ważna korekta matematyczna:** kwantyl 60. rozkładu ekskursji oznacza ok. **40% szansy dotknięcia** poziomu (P(M >= Q60) = 0.40), nie 60%. Dla docelowego prawdopodobieństwa dotknięcia p bierzemy kwantyl (1-p).
4. **Trend na 1-4h w BTC jest słaby i niestabilny** (badania pokazują wręcz istotną ujemną autokorelację zwrotów na 1h/2h/4h, czyli mean reversion; momentum jest udokumentowane dopiero na horyzoncie dziennym/tygodniowym). Wniosek projektowy: korekta trendowa BUY/SELL ma być **mała, ograniczona i podrzędna** wobec zmienności. Kierunek Twojej propozycji (uptrend: SELL dalej, BUY bliżej) jest zgodny z teorią (Avellaneda-Stoikov z dryfem), ale skala korekty musi być skalibrowana w backteście.
5. **Ekonomia fee jest twardym ograniczeniem:** Bybit spot 0.1% + 0.1% daje próg opłacalności cyklu ~0.20% gross. Minimalny sensowny spacing to ok. **0.28-0.30%** ceny (przy $65 000: ok. $180-200). Gridy ciaśniejsze niż to są matematycznie stratne.
6. **TradingView odpada jako źródło danych** (brak publicznego API, ToS zabrania użycia poza wyświetlaniem). Stack danych: **Binance Vision** (darmowe ZIPy 1m od 2017) na historię + **Bybit V5** (REST/WebSocket, publiczne bez klucza) na live, bo egzekucja będzie na Bybit.
7. **Backtest: własny, mały engine event-driven na świecach 1m** z trzema trybami symulacji fillów (optymistyczny / bazowy / stresowy) i walidacją walk-forward. Gotowe frameworki (vectorbt, backtrader, backtesting.py, freqtrade) nie obsługują poprawnie drabinki wielu jednoczesnych zleceń limit bez dopisywania własnej logiki, więc piszemy rdzeń sami, a gotowce zostają do sweepów parametrów.

---

## 2. Najważniejsze wyniki researchu

### 2.1 Podbudowa akademicka

| Ustalenie | Źródło | Implikacja dla systemu |
|---|---|---|
| Avellaneda-Stoikov (2008): kwotowania market makera powinny być rozstawione proporcjonalnie do zmienności, a środek przesunięty względem mid o karę za inventory; rozszerzenia dodają dryf (trend) | [Avellaneda & Stoikov, High-Frequency Trading in a Limit Order Book](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf) | Najbliższy rygorystyczny odpowiednik adaptacyjnego grida. Formuła środka: fair value + korekta dryfu + kara inventory. Trend i inventory to DWA OSOBNE mechanizmy, nie wolno ich mieszać w jeden |
| Symulacje A-S: skew inventory obniża wariancję P&L (std z 13.4 do 5.9), ale nie podnosi średniego zysku | jw. | Asymetria to głównie kontrola ryzyka, nie generator zysku. Ustawiać oczekiwania właśnie tak |
| BTC intraday: ujemna autokorelacja zwrotów pierwszego rzędu na 1h (-0.056), 2h (-0.086), 4h (-0.056), wysoce istotna; na 1D nieistotna | [De Nicola, On the Intraday Behavior of Bitcoin, Ledger 2021](https://ledgerjournal.org/ojs/ledger/article/download/213/212/1232) | Na horyzoncie grida (godziny) BTC średnio wraca, nie trenduje. To sprzyja gridowi i uzasadnia MAŁĄ wagę trendu |
| Momentum BTC istotne dopiero na horyzoncie dziennym i tygodniowym | [Liu & Tsyvinski, NBER w24877](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf) | Trend 1D jako kontekst tła (regime), nie jako korekta poziomów krótkiego grida |
| Asymetryczna rewersja: zwroty ujemne cofają się szybciej i silniej niż dodatnie | [Corbet & Katsiampa, Asymmetric mean reversion of Bitcoin price returns](https://shura.shu.ac.uk/23470/) | Kolejny argument za osobną estymacją D_h i U_h |
| Zmienność BTC: clustering, długa pamięć, skoki; modele HAR (komponenty 1h/1d/1w) najlepiej prognozują RV; skoki i structural breaks poprawiają prognozy | [Shen, Urquhart & Wang, EFM](https://onlinelibrary.wiley.com/doi/abs/10.1111/eufm.12254) | Skalowanie sqrt(t) z jednego okna to za mało; agregacja multi-timeframe w duchu HAR |
| Sezonowość dobowa: zmienność wyższa w godzinach EU/US, najniższa w nocy UTC; weekendy mają niższy wolumen i zmienność | wiele źródeł, m.in. [Finance Research Letters](https://www.sciencedirect.com/science/article/abs/pii/S1544612319301904) | Rozkłady ekskursji warto warunkować porą tygodnia (opcjonalnie, po walidacji) |

### 2.2 Stan wiedzy o adaptive grid (co istnieje, co mierzono)

| Implementacja / badanie | Logika spacingu | Ocena |
|---|---|---|
| [Chen, Chen & Jang 2025, Dynamic Grid Trading (arXiv preprint)](https://arxiv.org/html/2506.11921v1) | Geometric grid + recentrowanie po wybiciu zakresu; BTC/ETH 1m, 2021-2024 | Najbliższe opublikowane badanie BTC; raportuje dobre IRR, ale bez walk-forward, bez slippage, preprint. Recentrowanie (nie ATR) jest tym, co realnie testowano |
| [Yeh et al., Flexible Grid + ANN/SSO (peer-reviewed)](https://arxiv.org/pdf/2211.12839) | Nierówne, asymetryczne gęstości gridu optymalizowane co 30 dni | Jedyne recenzowane porównanie adaptive vs fixed; na indeksach akcyjnych (nie krypto); przewaga adaptive istnieje, ale bywa mała |
| [Binance Spot Grid "AI"](https://www.binance.com/en/support/faq/detail/76bd4effa3c4456c971a1c6835762742) | Zakres = MA +/- 3 sigma z 7/30/180 dni (Bollinger-style) | Jedyna giełda, która ujawnia formułę. To zwykła historyczna zmienność, żadne AI |
| Pionex AI 2.0, Bybit AI Strategy | Nieujawnione; rolling backtesty 7/30/180 dni | Czarne skrzynki, marketing |
| [Passivbot](https://github.com/enarjord/passivbot) | Spacing rośnie z ekspozycją (recursive), EMA bands | Inventory-adaptive, nie volatility-adaptive; ciekawy wzorzec dla drabinki |
| [Hummingbot Grid Executor](https://hummingbot.org/strategies/v2-strategies/executors/gridexecutor/) | Równe poziomy w zadanym zakresie + risk controls | Solidna referencja architektury egzekucji, spacing nie-adaptacyjny |
| [Quantpedia, A Primer on Grid Trading](https://quantpedia.com/a-primer-on-grid-trading-strategy/) | Dzienne recentrowanie, interwał = ułamek wczorajszej zmienności | Dobra ilustracja zależności od reżimu |

**Wniosek:** nikt nie opublikował wiarygodnego backtestu BTC, który izoluje "ATR-spacing vs dobrze dobrany fixed grid". Nasz backtest (sekcja 10) będzie więc realnie wnosił wiedzę, ale musi być zrobiony rygorystycznie, bo nie ma się na czym wzorować wprost.

### 2.3 Estymacja zmienności: co wybraliśmy i dlaczego

| Metoda | Werdykt |
|---|---|
| ATR | Zostaje TYLKO jako benchmark. Wady: brak interpretacji probabilistycznej, brak kierunku, mierzy zakres świecy (dwustronny), a nie jednostronną ekskursję; suma m ATR-ów silnie zawyża zakres wielogodzinny (dyfuzja skaluje się ~sqrt(m), nie m) |
| Realized volatility z 5m log-returns | **Rdzeń stanu zmienności.** 5m to standardowy kompromis między informacją a szumem mikrostruktury w badaniach BTC |
| Parkinson / Garman-Klass / Rogers-Satchell / Yang-Zhang | Teoretycznie efektywniejsze, ale ich przewagi zależą od sensownych open/close sesji, których BTC 24/7 nie ma. Parkinson na krótkich pod-świecach jako uzupełnienie robustness, nie rdzeń |
| **Empiryczne kwantyle ekskursji (U_h, D_h)** | **Główny silnik spacingu.** Bezpośrednio estymuje zdarzenie docelowe (dotknięcie bariery przed upływem h). Formalna podbudowa: first-passage time, wycena opcji barierowych, MFE/MAE |

---

## 3. Krytyczne słabości strategii (jako ograniczenia projektowe)

Nie dyskutujemy "czy", tylko wpisujemy do systemu obowiązkowe zabezpieczenia:

| Ryzyko | Wymóg systemowy |
|---|---|
| Akumulacja BTC w spadku (falling knife), kapitał uwięziony poniżej zakresu | Limity inventory (max % puli w BTC), metryka "time below range" w backteście, warunek NO TRADE przy ekspansji zmienności |
| Grid systematycznie sprzedaje BTC w hossie (opportunity cost vs hold) | Benchmark buy & hold + wariant 80/20 obowiązkowo w każdym backteście; raportujemy też wynik denominowany w BTC |
| Fee drag przy ciasnych gridach | Twardy floor: spacing >= Minimum Profitable Distance (sekcja 8); system nigdy nie zarekomenduje ciaśniej |
| Adverse selection (limit BUY wypełnia się tuż przed dalszym spadkiem) | Tryb stresowy backtestu + metryka post-fill markout |
| Niejednoznaczność świec OHLC (nie wiadomo, czy najpierw high czy low) | Symulacja na 1m z pesymistycznym porządkiem intrabar; wynik raportowany w 3 trybach |
| Overfitting parametrów | Mało parametrów, walk-forward, wybór plateau zamiast najlepszej komórki, nietykalny holdout |
| "Grid profit" ukrywa niezrealizowaną stratę inventory | Zawsze mark-to-market total equity, nigdy sam zrealizowany zysk cykli |
| Podatki PL | Zamiana krypto-krypto (BTC/USDT) jest wg ustawy o PIT neutralna podatkowo, podatek 19% dopiero przy wyjściu na fiat; to sprzyja gridowi BTC/USDT, ale **zweryfikuj z księgową** zanim wolumeny urosną |

---

## 4. Rekomendowany Volatility Engine

**Cel:** dla horyzontu h estymować rozkłady maksymalnej ekskursji w górę U_h i w dół D_h, warunkowo na reżimie.

Definicje (log-przestrzeń, potem konwersja na USD):

```
U_i(h) = max nad u w (0,h] : log(High_{t_i+u} / P_{t_i})
D_i(h) = max nad u w (0,h] : log(P_{t_i} / Low_{t_i+u})
```

**Minimalny zestaw wejść (4 cechy, nic więcej w V1):**

| Cecha | Implementacja |
|---|---|
| Fast RV | suma kwadratów 5m log-returns z ostatniej 1h |
| Slow RV | EWMA wariancji godzinowej z ostatnich 24h |
| Percentyl reżimu | bieżąca 4h RV (per-hour) na tle trailing 60-90 dni |
| Trend | znormalizowany slope OLS (sekcja 5) |

**Estymacja kwantyli:** empiryczne, ważone wykładniczo kwantyle U_h i D_h w koszykach reżimu (quiet / normal / elevated / extreme), osobno per horyzont h z {1, 2, 4, 8, 12, 24} godzin. Przy małej próbce koszyka: shrinkage do kwantyla bezwarunkowego.

**Zasady twarde:**

- Percentyl p dotknięcia = kwantyl (1-p) rozkładu. Chcesz ~50% szans filla w h: bierz medianę; ~40%: Q60.
- Obserwacje ekskursji z próbkowaniem co 5m silnie się nakładają: przedziały ufności przez block bootstrap, walidacja bez przetasowania.
- Ekstremów (prawdziwych skoków, świec likwidacyjnych) NIE winsoryzujemy; usuwamy tylko ewidentne bad ticks.
- Estymacja w log/procentach, konwersja na USD na końcu: `BUY = P * exp(-Q(D_h))`, `SELL = P * exp(+Q(U_h))`.

Okresy trailing (Twoje 24h/48h/72h/4d/7d): research wskazuje, że lepszy jest podział rola-zadanie: 1h (szok), 24h (baza), 60-90 dni (reżim). Okna pośrednie 48-96h nie wnoszą osobnej informacji przy modelu kwantylowym; sprawdzimy to w Phase 1 walidacji zamiast zakładać.

---

## 5. Rekomendowany Trend Engine

Jedna miara + jeden gate, nic więcej:

```
z_trend = (beta * h) / sigma_h
```

gdzie beta = slope OLS log ceny na ostatnich 12-24 obserwacjach 1h, sigma_h = prognozowana zmienność na horyzont h. Znak daje kierunek, |z_trend| siłę, a **R² regresji jest bramką**: przy niskim R² trend traktujemy jako zero (shrinkage).

Opcjonalne potwierdzenie (do przetestowania w Phase 1): użyj 1h slope tylko, gdy zgadza się ze znakiem slope 4h.

Odrzucone: ADX (podwójnie wygładzony, opóźniony, bez kierunku bez +DI/-DI, brak samodzielnej mocy predykcyjnej), EMA slope (zdominowany przez znormalizowany OLS), struktura HH/LL (tylko warstwa wizualna na dashboardzie).

---

## 6. Rekomendowany Market Regime Engine

Dwie osie, cztery stany zmienności, histereza:

| Oś | Stany | Reguła |
|---|---|---|
| Zmienność | quiet (<25 pct), normal (25-75), elevated (75-90), extreme (>90) | percentyl bieżącej 4h RV vs 60-90 dni; histereza ~5 pkt percentylowych przeciw migotaniu |
| Trend | brak / słaby / silny (znak +/-) | progi na |z_trend| z bramką R² |

Dodatkowy sygnał: **shock ratio** = fast RV (1h, per-hour) / slow RV (24h, per-hour). Ratio > ~2.0 oznacza ekspansję zmienności w toku (reżim się właśnie zmienia): stan przejściowy WAIT.

Klasyfikacja HMM/change-point: świadomie odłożona (koszt złożoności > zysk w V1).

---

## 7. GRID DECISION ENGINE V1

```
INPUTS
  cena P (Bybit mid), świece 1m/5m, config (fees, pula, horyzont h, target touch prob)
        |
CALCULATIONS
        |
VOLATILITY: fast RV, slow RV, kwantyle U_h / D_h per reżim
        |
TREND: z_trend (OLS slope / sigma), gate R²
        |
REGIME: percentyl vol + shock ratio + stan trendu
        |
BASE GRID DISTANCE
  d_buy  = P * (1 - exp(-Q_tau(D_h)))
  d_sell = P * (exp(+Q_tau(U_h)) - 1)
  (tau z targetu touch probability, np. p=0.45 -> tau=0.55)
        |
TREND ADJUSTMENT (mały, ograniczony)
  center shift = clamp(k * z_trend, -0.25, +0.25) * base distance
  uptrend: SELL dalej, BUY bliżej (zgodnie z A-S z dryfem)
  przy niskim R²: shift = 0
        |
BUY PRICE  = P - d_buy  - shift
SELL PRICE = P + d_sell + shift
        |
NO-TRADE FILTER (sekcja 7a)
        |
CONFIDENCE (scoring 0-95, sekcja 7b)
        |
OUTPUT: rekomendacja jak w briefie (BTC NOW / REGIME / BUY / SELL / ACTION / CONFIDENCE / REASON)
```

### 7a. Warunki NO TRADE / WAIT (konkretne progi startowe, do kalibracji)

| Warunek | Próg V1 | Werdykt |
|---|---|---|
| Zmienność extreme | percentyl 4h RV > 90 | NO TRADE |
| Ekspansja zmienności | shock ratio > 2.0 | WAIT (cooldown do spadku < 1.5) |
| Silny trend | \|z_trend\| > 1.5 przy R² > 0.5 | GRID NOT RECOMMENDED |
| Świeże wybicie | cena w ostatniej 1h wyszła poza high/low ostatnich 24h | WAIT (cooldown 2-4h) |
| Za niska zmienność | wyliczony spacing < 1.5 x Minimum Profitable Distance | NO TRADE (grid nie pokryje fees) |
| Event risk | manualna flaga w config (FOMC, CPI, halving-adjacent itp.) | WAIT |

### 7b. Confidence (deterministyczny scoring, bez ML)

Start 50 pkt; +20 reżim normal/quiet bez trendu; +10 shock ratio w [0.7, 1.3]; +10 spacing > 2x MPD; -20 elevated vol; -15 trend słaby-ale-obecny; -10 spread chwilowo rozszerzony; clamp do [0, 95]. Wagi do rewizji po backteście.

---

## 8. Fees: Minimum Profitable Grid Distance (MPD)

Dane (stan 2026-08, weryfikować przez API, nie hardkodować):

| Składnik | Wartość |
|---|---|
| Bybit spot maker/taker (non-VIP) | 0.10% / 0.10% (jedna strona pomocy pokazuje przykład 0.10/0.15: system MA czytać efektywną stawkę konta) |
| Break-even fee-only (round trip) | (1+0.001)/(1-0.001) = 1.002002, czyli ~0.2002% |
| Spread BTC/USDT top-of-book | ~0.1 USDT (~0.015 bp) przy normalnym rynku; rośnie z rozmiarem i w szokach |
| Binance (porównanie) | 0.10%/0.10%, z BNB 0.075%: fee-only ~0.15% |

Formuła:

```
MPD = P * (fee_buy + fee_sell + est_spread + slippage_buffer + min_net_profit)
```

Wartości startowe: fees 0.002, spread 0.0001, slippage buffer 0.0002, min_net_profit 0.0005, razem **~0.0028, czyli ~0.28%** (przy $65 000: ~$182). Reguła systemowa: rekomendowany spacing musi być >= 1.5 x MPD, inaczej NO TRADE. Zlecenia zawsze Post-Only (Bybit anuluje, jeśli miałoby wejść jako taker).

---

## 9. Grid Ladder (poziomy 2+)

Porównanie wariantów zostawiamy backtestowi, ale hipoteza robocza z researchu:

| Wariant | Ocena a priori |
|---|---|
| Fixed spacing (równe $) | benchmark, wymagany w backteście |
| Percentage spacing (geometric) | lepszy niż fixed $ (adaptuje się do poziomu ceny), drugi benchmark |
| **Volatility-adjusted expanding (rekomendacja V1)** | BUY_k / SELL_k z rosnących kwantyli dłuższych horyzontów: BUY1 = Q_tau(D_4h), BUY2 = Q_75(D_8h), BUY3 = Q_85(D_12h), BUY4 = Q_90(D_24h); głębsze poziomy są rzadziej dotykane, ale łapią większe ruchy. Odpowiednik "expanding spacing" (por. Passivbot recursive) z probabilistyczną interpretacją |
| Trend-adjusted | tylko jako mały shift środka (sekcja 7), nie osobna geometria drabinki |

Wielkości zleceń per poziom: V1 równe; wariant rosnący w głąb (jak w Twoim symulatorze akumulacji) do testu w Phase 7.

---

## 10. Przykład hipotetyczny: BTC = $65 000

**Liczby wejściowe są ilustracyjne (wymyślone na potrzeby przykładu), nie policzone z danych.**

Załóżmy: reżim normal (percentyl 55), shock ratio 1.1, z_trend = +0.6 przy R² 0.4 (słaby bullish, poniżej bramki: shift zredukowany), h = 4h, target touch p = 0.45 (tau = 0.55), Q_55(D_4h) = 0.52%, Q_55(U_4h) = 0.58%.

```
BTC NOW          $65 040

MARKET REGIME    Normal volatility (pct 55)
                 Mild bullish (below confidence gate)

RECOMMENDATION
BUY              $64 700     (BUY DISTANCE  -$340)
SELL             $65 420     (SELL DISTANCE +$380)

MPD CHECK        spacing 0.52% / 0.58% vs MPD 0.28%  -> OK (>1.5x)

ACTION           START GRID
CONFIDENCE       72%

REASON           Rozklad ekskursji 4h w rezimie normalnym wspiera
                 spacing $300-400. Trend lekko wzrostowy, ale ponizej
                 progu istotnosci (R² 0.4), wiec asymetria wynika glownie
                 z empirycznej roznicy rozkladow U/D, nie z korekty trendu.
```

---

## 11. Rekomendacja Data / API

| Rola | Wybór | Uzasadnienie |
|---|---|---|
| Historia (seed, TYLKO do walidacji i backtestu) | **Binance Vision** monthly ZIP, BTCUSDT 1m, od 2017 | darmowe, oficjalne, bulk; uwaga: od 2025-01 timestampy w mikrosekundach, normalizować przy ingest. Codzienna praca systemu NIE potrzebuje tej historii, tylko rolling 60-90 dni |
| Historia venue egzekucji | Bybit REST `/v5/market/kline` (max 1000/page, paginacja wstecz) | ostatnie ~2 lata 1m dla spójności z egzekucją |
| Live | Bybit V5 public WebSocket `kline.1.BTCUSDT` (+ opcjonalnie trades/orderbook dla spreadu) | publiczne bez klucza; limit REST 600 req/5s |
| Warstwa dostępu | CCXT do REST (normalizacja), natywny WS | CCXT nie omija limitów upstream; pinować wersję |
| Odrzucone | TradingView (brak publicznego API, ToS zabrania użycia non-display; tvdatafeed = ryzyko i max 5000 barów), Kraken REST (tylko 720 świec wstecz), CoinGecko (agregat, brak 1m), CryptoCompare/CoinDesk (free tier zlikwidowany 2026-05) | |
| Storage | Parquet partycjonowany `venue/symbol/year/month` + DuckDB do zapytań | proste, lokalne, szybkie |
| Zasada | **Nigdy nie sklejać świec Binance i Bybit w jedną serię**; Binance tylko jako fallback/reference z kolumną venue | różnice wicków i płynności psują kalibrację fillów |

---

## 12. Framework backtestingu

**Warianty do porównania (identyczny kapitał, fees, zakres czasu):**

- A. Fixed grid ($)
- B. ATR grid (k x ATR, k kalibrowane)
- C. Realized volatility grid (k x sigma_h)
- D. Percentile/excursion grid (nasz silnik, symetryczny)
- E. Adaptive excursion + trend + regime gate (pełny V1)
- Benchmarki: **buy & hold**, **80% hold + 20% grid E**, 50/50 rebalancing, DCA

**Silnik:** własny, event-driven, świece 1m:

- zlecenie utworzone na close minuty t aktywne najwcześniej od t+1
- 3 tryby fillów: optimistic (touch = fill), base (trade-through o 1 tick + pesymistyczna kolejność intrabar O-H-L-C vs O-L-H-C), stress (opóźnienia, częściowe fille, podwojone fees, poszerzony spread)
- fill nie może stworzyć zlecenia odwrotnego, które also fills w tej samej minucie, chyba że ścieżka intrabar to udowadnia
- pełne koszty: fee za fill, tick rounding, min notional Bybit

**Metryki:** total return (mark-to-market!), net po fees, liczba filli, ukończone cykle, zysk/cykl, max drawdown, expected shortfall, czas z uwięzionym kapitałem (below range), unrealized loss, ekspozycja BTC w czasie, turnover, wynik per reżim (bull/bear/sideways/breakout), wynik w denominacji BTC, degradacja out-of-sample.

**Walidacja anty-overfitting:** walk-forward (6-12 mies. IS, 1-3 mies. OOS, rolowanie), wybór plateau parametrów zamiast maksimum, nietykalny holdout (ostatnie ~3 mies.), raport wrażliwości na tryb fillów. Strategia, która działa tylko w trybie optimistic, jest odrzucana.

---

## 13. Architektura MVP: dwie warstwy o różnym tempie

**Wymóg Toma (2026-08-13): dashboard ma być dynamiczny.** Otwierasz go DZIŚ i dostajesz zalecany spread dla ceny z tej minuty. Historia wielu lat NIE jest potrzebna do codziennej decyzji; jest potrzebna tylko raz, do walidacji metody i backtestu.

| Warstwa | Co liczy | Dane | Częstotliwość |
|---|---|---|---|
| **A. Kalibracja (wolna, Python)** | tabele kwantyli Q(U_h)/Q(D_h) per reżim + progi percentyli reżimu | rolling 60-90 dni świec 1m/5m (lokalny cache Parquet, dosysanie przyrostowe) | raz dziennie (skrypt / Task Scheduler); tabele zmieniają się wolno |
| **B. Stan żywy (szybki, JS w dashboardzie)** | cena teraz, fast RV 1h, shock ratio, trend slope 1h/4h, lookup percentyla reżimu, poziomy BUY/SELL, MPD check, no-trade filter, confidence | ostatnie 24-48h świec + ticker z **publicznego API pobieranego przez przeglądarkę** (kilka requestów) | przy każdym otwarciu / kliknięciu Refresh |
| **C. Walidacja/backtest (jednorazowa + okresowa)** | dowód, że metoda działa; kalibracja progów | 2 lata historii 1m (Binance Vision + Bybit backfill) | Phase 1 i Phase 7; potem np. kwartalnie |

Przepływ produkcyjny:

```
(codziennie, cron)  calibrate.py: rolling 90 dni -> quantile_tables.json
(na zywo, browser)  index.html: fetch ticker + ostatnie 24-48h swiec
                    -> JS liczy fast RV / shock ratio / trend
                    -> naklada na quantile_tables.json (wbudowane w HTML lub obok)
                    -> rekomendacja BUY/SELL/ACTION/CONFIDENCE dla ceny z TEJ minuty
```

**Stack:** Python 3.11, pandas/numpy, requests/websockets, Parquet + DuckDB, pytest. Bez ML (research nie wykazał potrzeby; deterministyczne kwantyle są audytowalne).

**Dashboard: świadome odejście od Streamlit.** Single-file HTML (Chart.js), pattern Twoich istniejących dashboardów: zero serwera, działa z `file://`, deploy na GitHub Pages możliwy. Żywa warstwa liczona w JS, więc dashboard NIE wymaga uruchamiania Pythona do odczytu bieżącej rekomendacji; Python tylko odświeża kalibrację raz dziennie. Streamlit dopiero, jeśli zabraknie interaktywności (suwaki what-if).

**Ryzyko do sprawdzenia w Phase 2 (CORS):** nie mam pewności, czy publiczne endpointy Bybit V5 pozwalają na fetch z przeglądarki. Binance klines na pewno pozwala (powszechna praktyka client-side). Fallback bez utraty funkcji: żywa warstwa z Binance (cena BTC praktycznie identyczna), kalibracja i backtest na danych Bybit. Druga opcja fallback: mały `refresh.py` uruchamiany skrótem, który dopisuje snapshot do HTML.

---

## 14. Szczegółowy plan implementacji

| Faza | Cel | Kluczowe zadania | Input -> Output | Zależności | Główne ryzyko |
|---|---|---|---|---|---|
| **1. Research validation** | potwierdzić na danych 3 założenia zanim powstanie system | (a) policzyć rozkłady U_h/D_h i sprawdzić stabilność kwantyli w czasie, (b) zweryfikować kalibrację: czy Q_tau naprawdę jest dotykany z częstością ~(1-tau), (c) sprawdzić, czy koszyki reżimu różnicują rozkłady istotnie | 2 lata 1m Bybit -> notatnik + raport go/no-go | brak | kwantyle niestabilne między reżimami: wtedy prostszy model (k x sigma) |
| **2. Data layer** | powtarzalny lokalny magazyn świec | ingest Binance Vision, backfill Bybit REST, resampling 5m/1h/4h/1D, quality checks (gaps, duplikaty, low<=o/c<=high), repair job | API -> Parquet/DuckDB | brak | mikrosekundowe timestampy Binance od 2025; gaps Bybit |
| **3. Volatility Engine** | kwantyle U_h/D_h produkcyjnie | fast/slow RV, percentyl reżimu, ważone kwantyle z shrinkage, block bootstrap CI | świece -> `vol_state.json` | 1, 2 | overfitting koszyków przy małej próbce |
| **4. Trend Engine** | z_trend + gate | OLS slope 1h (12-24 obs), normalizacja sigma_h, R² gate, opcjonalna zgodność 4h | świece -> `trend_state.json` | 2 | fałszywe trendy przy skokach |
| **5. Market Regime Engine** | klasyfikacja + histereza | stany quiet/normal/elevated/extreme, shock ratio, detekcja wybicia 24h | 3, 4 -> `regime.json` | 3, 4 | migotanie stanów: histereza obowiązkowa |
| **6. Grid Decision Engine** | rekomendacja end-to-end | poziomy BUY/SELL (+ drabinka), MPD floor, no-trade filter, confidence, format outputu z briefu | 3-5 -> `recommendation.json` | 3, 4, 5 | zbyt częste zmiany rekomendacji: dodać minimalny czas życia rekomendacji |
| **7. Backtesting Engine** | porównanie A-E vs benchmarki | event-driven engine 1m, 3 tryby filli, walk-forward, raport per reżim | 2, 6 -> raporty HTML/CSV | 2, 6 | bar ambiguity; koszt obliczeń (numba/wektoryzacja hot path) |
| **8. Dashboard** | wizualizacja decyzji | single-file HTML: cena + poziomy, reżim, confidence, historia rekomendacji, wyniki backtestu | JSONy -> `index.html` | 6, 7 | przeładowanie informacją; wzorować na istniejących dashboardach |
| **9. Validation** | czy system ma realną wartość | holdout, forward test na żywych danych bez zleceń (min. 4-8 tygodni loga rekomendacji vs rzeczywistość), kalibracja confidence | 7, 8 -> decyzja go/no-go dla realnych zleceń | 7, 8 | wnioski z za krótkiego forward testu |

---

## 15. Struktura repozytorium

```
02-Projects/BTC Grid Engine/
├── CLAUDE.md
├── plan-v1.md                  # ten dokument
├── config/
│   └── settings.yaml           # fees, pula, horyzont, progi no-trade, flagi eventow
├── data/                       # gitignored
│   ├── raw/                    # ZIPy Binance Vision, dumpy Bybit
│   └── parquet/                # venue/symbol/year/month
├── src/
│   ├── data/                   # ingest_binance_vision.py, bybit_rest.py, bybit_ws.py, resample.py, quality.py
│   ├── volatility/             # rv.py, excursions.py, quantiles.py
│   ├── trend/                  # slope.py
│   ├── regime/                 # classifier.py
│   ├── grid_engine/            # levels.py, mpd.py, no_trade.py, confidence.py, recommend.py
│   ├── backtest/               # engine.py, fills.py, variants.py, walkforward.py, report.py
│   └── dashboard/              # build_html.py (JSON -> single-file index.html)
├── notebooks/                  # faza 1: walidacja zalozen
├── tests/
├── outputs/                    # recommendation.json, raporty backtestow
└── index.html                  # dashboard (generowany)
```

---

## 16. Pierwsze kroki w Claude Code (po zatwierdzeniu tego planu)

1. Utworzyć szkielet repo (struktura wyżej) + `config/settings.yaml` z fees/progami + `.gitignore` (data/).
2. `src/data/ingest_binance_vision.py`: pobranie BTCUSDT 1m monthly ZIP za ostatnie 24 miesiące, normalizacja timestampów, zapis Parquet.
3. `src/data/bybit_rest.py`: backfill Bybit spot BTCUSDT 1m za 24 miesiące (paginacja po 1000), osobna partycja venue=bybit.
4. `src/data/quality.py`: raport gapów/duplikatów/anomalii obu serii; decyzja, czy Bybit wystarczy jako jedyna seria kalibracyjna.
5. **Notebook walidacyjny Phase 1a:** policzyć U_h/D_h dla h={1,2,4,8,12,24}, wykresy rozkładów per reżim, tabela kwantyli.
6. **Notebook Phase 1b (kalibracja):** test wsteczny "czy Q_tau dotykany z częstością (1-tau)" walk-forwardowo; block bootstrap CI.
7. **Notebook Phase 1c:** porównanie wstępne spacing z ekskursji vs k x ATR vs k x sigma na prostym symulatorze single-pair (jeszcze bez pełnego engine).
8. Raport go/no-go z Phase 1 dla Ciebie: czy kwantyle są stabilne i skalibrowane; dopiero po Twoim OK ruszamy z fazami 3-6.
9. (Równolegle, tanie) `src/grid_engine/mpd.py` + odczyt efektywnych fees z Bybit API.
10. Decyzja Toma po kroku 8: zakres backtestu (ile wariantów drabinki, które okresy) przed budową pełnego engine.

---

## Źródła kluczowe

- [Avellaneda & Stoikov, High-Frequency Trading in a Limit Order Book (2008)](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf)
- [De Nicola, On the Intraday Behavior of Bitcoin, Ledger (2021)](https://ledgerjournal.org/ojs/ledger/article/download/213/212/1232)
- [Liu & Tsyvinski, Risks and Returns of Cryptocurrency, NBER w24877](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf)
- [Corbet & Katsiampa, Asymmetric mean reversion of Bitcoin price returns](https://shura.shu.ac.uk/23470/)
- [Shen, Urquhart & Wang, Forecasting the Volatility of Bitcoin (EFM)](https://onlinelibrary.wiley.com/doi/abs/10.1111/eufm.12254)
- [Chen, Chen & Jang, Dynamic Grid Trading Strategy (arXiv 2506.11921, preprint)](https://arxiv.org/html/2506.11921v1)
- [Yeh et al., Flexible Grid Trading Model (ANN + SSO)](https://arxiv.org/pdf/2211.12839)
- [Quantpedia, A Primer on Grid Trading Strategy](https://quantpedia.com/a-primer-on-grid-trading-strategy/)
- [Binance Spot Grid: metodologia parametrów AI](https://www.binance.com/en/support/faq/detail/76bd4effa3c4456c971a1c6835762742)
- [Bybit V5 API: kline](https://bybit-exchange.github.io/docs/v5/market/kline), [rate limits](https://bybit-exchange.github.io/docs/v5/rate-limit), [Post-Only](https://www.bybit.com/en/help-center/article/Post-Only-Order), [Spot Grid P&L](https://www.bybit.com/en-GB/help-center/article/Profit-Loss-Calculations-Spot-Grid-Bot)
- [Binance Vision: publiczne archiwum klines](https://github.com/binance/binance-public-data/blob/master/README.md)
- [TradingView: brak publicznego data API](https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/)
- [Hummingbot Grid Executor](https://hummingbot.org/strategies/v2-strategies/executors/gridexecutor/), [Passivbot](https://github.com/enarjord/passivbot)
- Bar ambiguity / fill modeling: [ohlcv.io backtesting pitfalls](https://ohlcv.io/posts/backtesting-pitfalls/04-bar-resolution/), [limit order fill probability](https://www.quantmemo.com/concepts/limit-order-fill-probability)

Pełne listy cytowań (3 raporty Perplexity) zachowane w transkryptach sesji 2026-08-13.
