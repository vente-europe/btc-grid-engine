# BTC Grid Decision Engine: plan V2 (scalony i uproszczony)

> 2026-08-13. Scalenie trzech planów: Claude (plan-v1.md, tam pełny research i źródła), ChatGPT, agent Toma. Zasada scalania: **maksymalnie proste, byle na końcu odpowiadało na jedno pytanie: jaki spread jest optymalny TERAZ.**
>
> plan-v1.md zostaje jako archiwum researchu (cytowania, uzasadnienia). Ten dokument jest wiążący.

---

## 1. Co system robi (jedno zdanie)

Otwierasz dashboard i widzisz dla ceny z tej minuty: zalecany BUY, zalecany SELL, spread, czy w ogóle startować i dlaczego.

```
BTC NOW          $65 040
ENVIRONMENT      GOOD   (zmiennosc: normalna, oscylacja: wysoka, trend: lekko w gore)

WARIANTY SPREADU
  CONSERVATIVE   BUY $64 480   SELL $65 640   (rzadsze transakcje, wiekszy zysk/cykl)
  BALANCED  <--  BUY $64 700   SELL $65 420   (rekomendowany)
  AGGRESSIVE     BUY $64 820   SELL $65 300   (czestsze transakcje, fees zjadaja wiecej)

ACTION           START GRID
CONFIDENCE       72/100
PRZELICZ GDY     cena wyjdzie poza $63 900 - $66 200 lub zmieni sie rezim zmiennosci
```

---

## 2. Jak liczymy spread (serce systemu)

**Nie ATR, tylko realne ruchy.** Dla każdej minuty z ostatnich 60-90 dni sprawdzamy: jak daleko cena faktycznie odjechała w górę i w dół w ciągu następnych H godzin. Z tego powstają dwa rozkłady (ruchy w górę i w dół osobno) i ich percentyle:

```
Przyklad (dane wymyslone):
  ruch w dol w 4h:  P50 = $290   P60 = $340   P70 = $420
  ruch w gore w 4h: P50 = $310   P60 = $380   P70 = $460
```

Trzy warianty z jednej tabeli:

| Wariant | Percentyl | Znaczenie |
|---|---|---|
| AGGRESSIVE | P50 | poziom dotykany w ok. 50% przypadków |
| BALANCED | P60 | ok. 40% przypadków (rekomendowany start) |
| CONSERVATIVE | P70 | ok. 30% przypadków |

Ważne (częsty błąd): P60 oznacza ok. **40%** szansy dotknięcia, nie 60%.

Horyzonty w V1: **1h, 4h, 24h** (domyślny do decyzji: 4h). Bez macierzy 4 timeframe x 3 okresy: to warstwa "wyjaśnij mi", nie decyzja.

---

## 3. Oscylacja: czy rynek faluje, czy jedzie (nowe, z planu ChatGPT)

Zmienność nie wystarczy. Dzień, w którym BTC lata 65000 - 64500 - 65100 - 64600 jest świetny dla grida; dzień 65000 - 64500 - 64000 - 63500 jest fatalny, a "zmienność" może być identyczna.

**Oscillation Score (0-100):** jaka część drogi przebytej przez cenę to falowanie, a jaka trwałe przesunięcie.

```
score = 100 * (1 - |przesuniecie netto 24h| / suma |ruchow| 24h)
```

Interpretacja: 80+ świetny rynek gridowy, 50-80 umiarkowany, <50 rynek kierunkowy (ostrożnie), <30 silny trend (nie graj).

To najtańsza w obliczeniu i najbardziej intuicyjna metryka w całym systemie. Wchodzi do reżimu i do confidence.

---

## 4. Trend: jedna miara, mała korekta

Jeden wskaźnik: **nachylenie regresji log ceny z ostatnich 12-24h, znormalizowane zmiennością**, z R² jako bramką (słabe dopasowanie = trend traktujemy jako zero).

Zastosowanie: tylko przesunięcie asymetrii, nigdy zmiana całkowitego ryzyka:

```
korekta = clamp(0.25 * sila_trendu, -25%, +25%) bazowego dystansu
trend w gore: SELL dalej, BUY blizej (i odwrotnie)
```

Wycięte z planów ChatGPT/agenta: ADX, EMA 20/50 + EMA 50/200, 4-składnikowe wagi trend_score. Research (v1, sekcja 5): ADX bez samodzielnej wartości predykcyjnej, a BTC na 1-4h i tak średnio wraca, nie trenduje. Jedna miara wystarczy.

---

## 5. Reżim i kiedy NIE grać

Trzy wejścia: percentyl zmienności (bieżąca 4h vs ostatnie 60-90 dni), Oscillation Score, trend.

| Sytuacja | Decyzja |
|---|---|
| Zmienność normalna/podwyższona + wysoka oscylacja | **START GRID** |
| Zmienność ekstremalna (percentyl > 90) | NO TRADE |
| Nagła ekspansja zmienności (1h vol > 2x średnia 24h) | WAIT |
| Silny trend (oscylacja < 30 lub \|trend\| duży przy dobrym R²) | NO TRADE |
| Świeże wybicie poza high/low ostatnich 24h | WAIT (2-4h) |
| Wyliczony spread < 1.5 x minimum opłacalności | NO TRADE |
| Flaga eventu w configu (FOMC, CPI) | WAIT |

System MUSI często mówić WAIT. To nie błąd, to feature.

---

## 6. Minimum opłacalności (twardy próg)

Bybit spot 0.1% + 0.1%: sam koszt cyklu to ~0.20%. Z buforem na spread i poślizg:

```
MPD = ~0.28% ceny        (przy $65 000: ~$182)
regula: rekomendowany spread >= 1.5 x MPD, inaczej NO TRADE
```

Zlecenia zawsze Post-Only (wymusza fee maker, Bybit anuluje zamiast wykonać jako taker). Fees czytane z API, nie hardkodowane.

---

## 7. Drabinka (poziomy 2+): rozszerzające się mnożniki

Prosto, bez osobnych kwantyli na każdy poziom (uproszczenie z planu agenta):

```
BUY1  = cena - 1.00 x dystans_buy      SELL1 = cena + 1.00 x dystans_sell
BUY2  = cena - 1.75 x dystans_buy      SELL2 = cena + 1.75 x dystans_sell
BUY3  = cena - 2.75 x dystans_buy      SELL3 = cena + 2.75 x dystans_sell
BUY4  = cena - 4.00 x dystans_buy      SELL4 = cena + 4.00 x dystans_sell
```

Dlaczego rozszerzające: głębsze poziomy rzadziej dotykane, ale chronią przed łapaniem noża i pasują do grubych ogonów BTC. Mnożniki do walidacji w backteście. Wielkości zleceń w V1 równe; proporcje kapitału BUY/SELL zależne od trendu (55/45 itd.): dopiero V2, po backteście.

---

## 8. Kiedy przeliczyć rekomendację

Rekomendacja nie żyje wiecznie. Przelicz gdy:

- cena wyjdzie poza zakres drabinki (recentrowanie, jak w badaniu Dynamic Grid Trading),
- zmieni się reżim zmienności (przekroczenie progu percentyla z histerezą),
- minie 12h od wydania,
- odpali którykolwiek warunek WAIT/NO TRADE.

---

## 9. Samoocena systemu (z planu ChatGPT, tanie i cenne)

Każda rekomendacja zapisywana do loga (JSON): czas, cena, spread, reżim, confidence. Skrypt raz dziennie sprawdza: czy BUY/SELL zostały dotknięte w 1h/4h/24h. Po 2-3 miesiącach mamy własną odpowiedź na pytanie "czy P60 naprawdę znaczy ~40%" i twarde dane do kalibracji confidence. Zero dodatkowej infrastruktury: plik JSONL + skrypt.

---

## 10. Dane i architektura (dynamiczna, dwie warstwy)

| Warstwa | Co | Kiedy |
|---|---|---|
| Kalibracja (Python) | tabele percentyli ekskursji + progi reżimu z rolling 60-90 dni | raz dziennie (Task Scheduler) |
| Live (JS w dashboardzie) | cena teraz, ostatnie 24-48h świec z publicznego API, oscylacja, trend, poziomy, confidence | przy każdym otwarciu/odświeżeniu |

- Dashboard: **single-file HTML** (pattern pozostałych dashboardów Toma), bez Streamlit, bez serwera. Otwierasz plik, po 2-3 s masz rekomendację dla ceny z tej minuty.
- Dane historyczne (tylko walidacja + backtest, jednorazowo): Binance Vision ZIP 1m + backfill Bybit REST.
- Live: Bybit V5 public API (venue egzekucji); fallback Binance jeśli CORS zablokuje fetch z przeglądarki.
- Storage: Parquet + DuckDB. TradingView: nie (brak API, ToS).

---

## 11. Backtest (bez tego dashboard to tylko ładny kalkulator)

Porównujemy na identycznych warunkach: A fixed grid, B ATR grid, C realized vol grid, D percentile grid (nasz, symetryczny), E pełny adaptive (D + trend + reżim). Benchmarki: **buy & hold**, **80% hold + 20% grid E**, cash.

Zasady uczciwości: świece 1m, trzy tryby wypełnień (optymistyczny / bazowy / stresowy), pełne fees, walk-forward, nietykalny holdout, wybór stabilnych plateau parametrów zamiast najlepszej komórki. Strategia działająca tylko w trybie optymistycznym = odrzucona. Kluczowe pytanie walidacyjne (za agentem): **czy 80/20 z gridem bije 100% hold po kosztach i drawdownie**, nie "czy grid zarobił".

---

## 12. Czego świadomie NIE robimy w V1 (lista cięć)

| Wycięte | Skąd | Dlaczego |
|---|---|---|
| Rolling backtest optimizer spreadu co kilka minut | ChatGPT pkt 10 | najciekawszy pomysł na V3, ale ciężki i podatny na overfitting; percentyle ekskursji to prostszy odpowiednik |
| ADX, EMA 20/50/200, wieloskładnikowe trend_score i vol_score | ChatGPT + agent | jedna znormalizowana regresja robi to samo prościej |
| Macierz 4 timeframe x 3 okresy jako podstawa decyzji | brief + ChatGPT | zostaje co najwyżej jako rozwijana sekcja "pokaż szczegóły" |
| Kraken / Coinbase cross-checki | agent | zbędna złożoność; Bybit + Binance wystarczą |
| Podział kapitału 55/45 wg trendu | ChatGPT pkt 9 | dopiero po backteście (obaj autorzy zresztą to zastrzegli) |
| Streamlit | agent | Tom wymaga dynamicznego single-file HTML |
| ML / HMM / order book microstructure / live trading | wszyscy zgodnie | V1 ma być audytowalny i prosty |
| 6 horyzontów ekskursji | plan v1 | tniemy do 3 (1h / 4h / 24h) |

---

## 13. Fazy (skrócone)

| Faza | Co | Wynik |
|---|---|---|
| 1. Walidacja | policzyć percentyle ekskursji na 2 latach danych; sprawdzić czy P60 naprawdę = ~40% dotknięć; czy koszyki reżimu różnicują | raport go/no-go dla Toma |
| 2. Dane | ingest Binance Vision + Bybit, quality check, resampling | lokalny magazyn Parquet |
| 3. Silniki | ekskursje + oscylacja + trend + reżim + decyzja (pure functions, JSON) | `recommendation.json` |
| 4. Backtest | warianty A-E vs benchmarki, walk-forward | raport + kalibracja progów |
| 5. Dashboard | dynamiczny single-file HTML (warstwa live w JS) | `index.html` |
| 6. Forward test | 4-8 tygodni loga samooceny na żywych danych | decyzja o realnych zleceniach |

## 14. Pierwsze kroki w Claude Code (po zatwierdzeniu)

1. Szkielet repo + `config/settings.yaml` (fees, horyzonty, progi) + `.gitignore`.
2. Ingest Binance Vision (24 mies. 1m) + backfill Bybit REST; quality report.
3. Notebook: rozkłady ekskursji 1h/4h/24h + Oscillation Score na historii; wykresy per reżim.
4. Notebook: kalibracja wsteczna (czy P60 dotykany ~40% razy, walk-forward).
5. Raport go/no-go dla Ciebie. Dopiero po OK: silniki, backtest, dashboard.

---

## Decyzje scalenia (skąd co pochodzi)

| Element V2 | Źródło |
|---|---|
| Percentyle ekskursji jako serce spacingu | zgodne wszystkie trzy plany |
| Oscillation Score | ChatGPT (adoptowane w całości) |
| Warianty Conservative / Balanced / Aggressive | ChatGPT (tanie: 3 percentyle z jednej tabeli) |
| Samoocena (log rekomendacji + wynik po 1h/4h/24h) | ChatGPT (uproszczone do JSONL + skrypt) |
| Reguły przeliczenia rekomendacji (recentrowanie) | ChatGPT / badanie DGT |
| Drabinka z mnożnikami 1.0 / 1.75 / 2.75 / 4.0 | agent |
| Progi confidence (<40 NO TRADE, 40-55 WAIT, 55-70 słaby, 70-85 OK, 85+ mocny) | agent |
| Kluczowe pytanie backtestu (80/20 vs 100% hold) | agent |
| Jedna miara trendu (OLS slope + R² gate), bez ADX | Claude v1 (research) |
| P60 = ~40% dotknięć (korekta kierunku percentyla) | Claude v1 |
| Dwuwarstwowa architektura + dynamiczny HTML | Claude v1 + wymóg Toma |
| Bybit jako venue + MPD ~0.28% | Claude v1 (Tom handluje na Bybit) |
