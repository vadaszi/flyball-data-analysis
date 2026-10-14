# Excel Data Structure – Technical Reference

This file describes how the three source Excel files are **physically** laid out, as found by inspection on 2026-10-13. It complements `WRFT_dokumentacio.md` (the client's official data dictionary) with everything that file does not say: cell layout, hidden formatting, per-sheet facts and known anomalies. The source files must never be modified.

Reading requirement: **`openpyxl`** (or another reader that exposes cell styles). Lane colour and fault markers live in **font colours**, which `pandas.read_excel` alone loses.

---

## 1. `Wild_Runners_Flyball_Team_kutyak_alapadatai.xlsx` – dog master data

- 1 sheet: `Munkalap1`. Header in row 1, **51 data rows (rows 2–52)**. Rows 53–968 are empty but formatted; skip them.
- Columns A–I as documented. Columns J–Q exist (empty, formatted) and should be ignored.
- One row per dog. Handler (`felvezeto`), name (`nev`) and chip number are each unique (51/51). **The dog name is the join key** to the competition data. Use it only inside WRFT team rows (see §2.6).

| Column | Stored as | Notes |
|---|---|---|
| `felvezeto` | text | 2 letters + 6 digits |
| `nev` | text | unique |
| `fajta` | text | Inconsistent spelling: `Border Collie` (15), `Border` (5), `border collie` (3), `BorderCollie` (3), `Mix` (5), `Keverék` (3), `Australian Shepperd` (typo), plus single breeds |
| `nem` | text | `kan` / `szuka` |
| `ivar` | text | `ivaros` / `ivartalan`. Counts: neutered male 22, neutered female 19, intact male 8, **intact female 2** |
| `szuletesi_datum` | **Excel serial number** (e.g. 40223 = 2010-02-14) | Convert with origin 1899-12-30 |
| `chip_szam` | text, 14 digits | Keep as string |
| `ulna_hossz` | number (cm) | **4 entry errors**: Speedy 1.491 → 14.91, Henry 1.209 → 12.09, Bruno 175.5 → 17.55, Falco 152.8 → 15.28. All four are confirmed by the FCI ulna table (see `domain_knowledge.md` §4) |
| `ugrasi_magassag` | number (cm) | Values 15, 20, 22.5, 25, 27.5, 30, 32.5. Matches the FCI table for 49/51 dogs; Punk and Hank sit on a band edge. Treat as authoritative |

- **Fibo** never appears in any 2023 competition.

---

## 2. Competition workbooks – common layout

Both `FLYBALLCZ_versenyadatok.xlsx` (12 sheets) and `EFC_versenyadatok.xlsx` (4 sheets) use the **same 20-column layout**. Only the header language differs.

### 2.1 Rows
- **Row 1:** title in **cell B1**: `"<competition> (<venue>) 2023. <month> <days>."`. Parse it for the competition name, venue and dates.
- **Row 2:** column headers starting in B2. Cell A2 is empty, except in `Křupky na břehu`, where A2 = `"X"`.
- **Row 3 onward:** data. EFC sheets have 1000 formatted rows, of which only the first 197–370 contain data. Filter out rows without a team name. **Don't stop at the first empty row:** `Eager´s Cup 1` and `Eager´s Cup 2` have one blank separator row at the day break (see `ANALYSIS_LOG.md` Step 1.1).
- **One row = one team in one heat.** A heat is two consecutive rows (team and opponent) with the same timestamp. The opponent's row has the same structure, with `kdo` and `s kým` swapped.

### 2.2 Columns (by position)

| Col | CZ header | EFC header | Meaning |
|---|---|---|---|
| A | (none) | (none) | Running row number within the sheet (`nevtelen`) |
| B | `Divize` | `Division` | Division number |
| C | `kdy` | `when` | Time as an Excel day fraction. CZ: 0.33–0.79, the **time of day only**. EFC: 1.33–1.77, i.e. 1 + fraction; both EFC days use the 1.x prefix, so use only the fractional part and take the day from the sheet name |
| D | `kdo` | `who` | Team of this row. **Font colour = lane colour** (§2.3) |
| E | `s kým` | `with who` | Opponent team |
| F | `celkem` | `total time` | Team total time (s) |
| G | `V/P/R` | `W/L/T` | Outcome. EFC sheet 2 (`EFC_1 ring_2`) uses Czech `V/P` |
| H | `překážky` | `Hurdles` | Hurdle height (cm) |
| I | `jméno` | `name` | Dog 1 name (olive font) |
| J | `start` | `start` | Dog 1 start time |
| K | `1.pes` | `1.dog` | Dog 1 run time |
| L | `jméno` | `name` | Dog 2 name |
| M | `stříd.` | `chng` | Dog 2 changeover |
| N | `2.pes` | `2.dog` | Dog 2 run time |
| O | `jméno` | `name` | Dog 3 name |
| P | `stříd.` | `chng` | Dog 3 changeover |
| Q | `3.pes` | `3.dog` | Dog 3 run time |
| R | `jméno` | `name` | Dog 4 name |
| S | `stříd.` | `chng` | Dog 4 changeover |
| T | `4.pes` | `4.dog` | Dog 4 run time |

- **The column headers repeat** (`jméno` ×4, `stříd.` ×3), so read by **position**, not by header name.
- Some sheets have formatted but empty columns beyond T (up to col 34 in Eager's Cup). Ignore them.
- Numbers carry float noise (e.g. `17.010000000000002`, `7.0000000000000007E-2`). Round to 3 decimals after parsing.

### 2.3 Information hidden in cell formatting (font colour)

**Lane colour: font colour of column D (team name).**

| File | Red lane | Blue lane |
|---|---|---|
| FLYBALLCZ | `rgb=FFFF0000` | `rgb=FF0000FF` |
| EFC | `indexed=11` | `indexed=15` |

- The EFC workbook defines a **custom `indexedColors` palette** in `styles.xml`, where index 11 = `ff0000` (red) and index 15 = `0000ff` (blue). Don't assume the default Excel palette.
- Every sheet is split almost exactly 50/50 between red and blue rows.
- The FCI rules require the two hurdle sets to be different colours, preferably red and blue, so this is the "pálya színe" (lane colour) of Question 1.

**Fault marker: red font on time cells (columns J–T).**
- CZ uses `rgb=FFFF0000`; EFC uses `indexed=11`.
- Verified: every red cell is either a negative number or a fault text (`mimo`, `vběhl`, `chyba`, `error`, `outside`, `run in`). No numeric-looking value is marked red, so the values themselves are sufficient to detect faults. The red font is a useful cross-check only.

**Other fonts:**
- Dog-name columns (I, L, O, R) are olive: `rgb=FF808000` in CZ, `indexed=16` in EFC.
- Normal values are black: `theme=1` in CZ, `indexed=8` in EFC.

### 2.4 Special values in time columns

| Value(s) | Columns where it appears | Meaning |
|---|---|---|
| `ok`, `OK`, `Ok` | changeover; once in a run column | ≈0.00 s pass ("perfect") |
| `chyba` (CZ) / `error` (EFC) | changeover; once in a run column | early pass detected but not quantified |
| `mimo` (CZ) / `outside` (EFC) | run; EFC sheet 2 also in Czech | dog went outside / missed a hurdle |
| `vběhl` (CZ) / `run in` (EFC) | run; **also appears in changeover columns** (misplaced) | dog ran in / behind the box |
| negative number | start | false start |
| negative number | changeover | early pass, quantified |
| negative number | run (rare: e.g. -2.44, -2.2, -0.78) | invalid value; treat as an error |
| empty | any | not recorded. Common in changeovers after a fault, and for dogs that didn't run |

**Value ranges:**

| Measure | Range | Normal value |
|---|---|---|
| Total time | 0 – 86 s | ≈15–25 s |
| Start | -1.55 – 25.58 s | ≈0–0.3 s |
| Run | -2.44 – 73.38 s | ≈3.5–6 s |
| Changeover | -1.53 – 45.91 s | ≈0–1 s |

### 2.5 Incomplete and abnormal rows
- **Shifted rows:** in 19 rows a `vběhl` in a changeover cell is followed by values one cell too early. This is the source of the negative run times and of the `ok`/`chyba` codes in run columns (`ANALYSIS_LOG.md` Step 1.4).
- **Rows with fewer than 20 filled cells:** 17–125 per sheet. They come in four types:
  - **(a) Single-dog rows** with a ~4–5 s total and no outcome. These are very likely **practice starts** (FCI §2.05d), e.g. the first rows of Eager's Cup 1, Máchale and Budějckej 2.
  - **(b) Heats where fewer than 4 dogs ran.**
  - **(c) Rows where only one changeover cell is empty** (common).
  - **(d) EFC rows with missing dog names**, e.g. Yelly BEAST, Quickstep!
- **Missing outcome:** up to 19 rows per sheet. **Total time = 0:** in several sheets.
- `Budějckej xtreme 2`, rows 1–2: the dog name is `"0"` and the hurdle height is empty.
- **Total time identity:** `total = start + Σ4 runs + Σ3 changeovers` (with `ok` = 0) holds within ±0.02 s for **87.7 %** of the 6,286 fully numeric rows. A larger total means a faulted dog ran again.

### 2.6 Team and dog names
- **WRFT teams** all start with `WildRunners` (consistent spelling): `Maximini`, `Nightfall`, `Wonders`, `XXL`, `Zephyr`, `dreamers`, `hopefuls`. Seven teams in total.
- **WRFT vs WRFT heats** exist: 105 rows in Hanácké, 72 in BCCCZ, 20 in MČR, 10 in Eager's Cup 1.
- **Name collisions:** the masked dog names are **not unique across the whole dataset**.
  - Placeholder names `Chase`, `Rubble`, `Zuma` and `Marshall` appear in several unrelated teams (Real Ballance, Flyvaryors Kamikaze, Frenky's Funny, New Ballance).
  - Opponent teams have dogs called `Abby`, `Easy`, `Scotty` and others, which are also WRFT names.
  - → **Identify WRFT dogs only within rows where `kdo` starts with `WildRunners`.** In those rows, every dog name matches the master data: 50 of 51 dogs appear, and there are no unknown names.
- **Case variants** in other teams' names, e.g. `HELLODOGS NEW GENERATION`, `amy`/`Amy`, `RUNAMI A`/`RUNami A`, `Jokers ALL-IN`/`Jokers All-in`. Normalise case when grouping opponents.
- **WRFT line-ups are fluid:** 40 of 50 dogs ran in more than one WRFT team during the season.

---

## 3. Per-sheet facts

"WR rows" = rows where the team (`kdo`) is a WRFT team. "Day-2 starts at" = the 0-based index, within the data rows, of the first row after the overnight drop in time of day. Each 2-day CZ sheet has exactly one such drop.

| File / sheet | Competition (venue) | Dates (as given) | Data rows | WR rows | WR teams present | Divisions | Day-2 starts at |
|---|---|---|---|---|---|---|---|
| CZ `Hanácké škvarek` | Hanácké škvarek (Heroltice) | 2023-04-22/23 | 235 | 161 | dreamers, Maximini, hopefuls, XXL, Zephyr, Nightfall | 1, 2 | 109 |
| CZ `Eager´s Cup 1` | Eager's Cup, ring 1 (Žamberk) | 2023-05-06/07 | 641 | 120 | XXL, Zephyr, Nightfall, dreamers, hopefuls | 1, 2, 4, 8 | 312 |
| CZ `Eager´s Cup 2` | Eager's Cup, ring 2 (Žamberk) | 2023-05-06/07 | 705 | 21 | Maximini | 3, 5, 6, 7 | 329 |
| CZ `Flyvaryors turnaj` | Flyvaryors turnaj (Blšany) | 2023-05-20/21 | 740 | 81 | Zephyr, Maximini, hopefuls | 1–5 | 354 |
| CZ `MED's Trophy` | MED's Trophy (Pláně) | 2023-06-10/11 | 579 | **0** | — | 1–4 | 284 |
| CZ `BCCCZ mistrovství` | BCCCZ championship (Prostějov) | 2023-06-24/25 | 389 | 184 | all 7 | 1, 2, 3 | 184 |
| CZ `Crazy Cup` | Crazy Cup (Nové Město pod Smrkem) | 2023-07-01/02 | 824 | 149 | XXL, Zephyr, Maximini, Nightfall, dreamers, hopefuls | 1–6 | 386 |
| CZ `Máchale, spadlo ti to!` | Máchale… (Louňovice) | 2023-07-15/16 | 668 | 75 | Zephyr, XXL, Maximini | 1–5 | 314 |
| CZ `Mistrovství České republiky` | Czech championship (Blšany) | **2023-09-03/04 ⚠** | 521 | 113 | Zephyr, Nightfall, hopefuls, dreamers, Maximini | 1–4 | 241 |
| CZ `Křupky na břehu` | Křupky na břehu (Litomyšl) | 2023-09-16/17 | 607 | 93 | dreamers, Zephyr, Maximini, hopefuls | 1–4 | 290 |
| CZ `Budějckej xtreme 1` | Budějckej xtreme, ring 1 (Vodňany) | 2023-10-14/15 | 728 | **0** | — | 1, 3, 6, 7 | 338 |
| CZ `Budějckej xtreme 2` | Budějckej xtreme, ring 2 (Vodňany) | 2023-10-14/15 | 758 | 72 | Wonders, Maximini, dreamers | 2, 4, 5, 8 | 356 |
| EFC `EFC_1 ring_1` | EFC, ring 1 (Tápiószentmárton, HU) | 2023-07-29 | 268 | 15 | Zephyr | 10, 11, 13 | — |
| EFC `EFC_1 ring_2` | EFC, ring 2 | 2023-07-29 | 197 | 23 | Nightfall | 9, 12 | — |
| EFC `EFC_2 ring_1` | EFC, ring 1 | 2023-07-30 | 370 | 14 | dreamers, hopefuls | 1–4 | — |
| EFC `EFC_2 ring_2` | EFC, ring 2 | 2023-07-30 | 341 | 7 | Maximini | 5–8 | — |
| **Total** | 11 competitions | | **8,571** | **1,128** | | | |

**Notes:**
- **⚠ Czech championship date:** 3–4 Sep 2023 is a Sunday–Monday, while all other events run Saturday–Sunday. **Resolved in Step 1.9:** the event was held on 2–3 Sep 2023, confirmed by a club results page whose best times match this sheet exactly. The correction lives in `config.DATE_OVERRIDES`.
- **Ambiguous venues:** Heroltice, Louňovice and Pláně exist more than once in the Czech Republic, and so does Blšany. **Resolved in Step 3.1** from the events' own pages. The coordinates are in `config.VENUES`.
- **EFC sheet 2** (`EFC_1 ring_2`) uses Czech fault texts (`mimo`, `chyba`) and Czech outcomes (`V`/`P`).
- **Sheets without WRFT teams** (MED's Trophy, Budějckej 1) still contain the full field. They are usable as a benchmark and for testing the lane-colour and weather effects on all dogs.
