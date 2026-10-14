# WRFT Flyball Analysis – Working Log

Every step performed on the dataset is recorded here: **what** was done, **why**, and its **effect** (rows or values affected). Entries are added as the work happens, newest at the bottom. The original Excel files are never modified; all changes happen in code.

---

## Step 0 – Initial exploration and domain research (2026-10-13)

No data has been changed in this step. These are read-only checks done before cleaning, to understand the data.

### 0.1 Data inventory
- **What:** Read all 3 Excel files with a minimal read-only reader. Python packages were not installed yet.
- **Findings:**
  - Dog master data: 1 sheet, 51 dogs. The sheet has 968 rows, but rows 53+ are empty formatting.
  - FLYBALLCZ: 12 sheets covering 10 competitions (Eager's Cup and Budějckej xtreme have 2 rings each).
  - EFC: 4 sheets (2 days × 2 rings).
  - About 8,500 data rows in total. **All teams in each competition are included**, not only WRFT.
- **Why:** to know the structure before designing the cleaning step.

### 0.2 Hidden information in cell formatting
- **What:** Inspected cell styles (font and fill colours) per column.
- **Findings:**
  - **Lane colour** is not a column. It is encoded as the **font colour of the team-name cell**: red or blue. In the EFC file this uses a custom palette, where index 11 = red and 15 = blue. Each sheet is split almost exactly 50/50.
  - **Red font on time cells marks faults.** Cross-check: every red cell is either a negative number or a fault text, so no fault is hidden behind a normal-looking number.
- **Why:** Question 1 (lane colour) can only be answered from this formatting. `openpyxl` is required to read it.

### 0.3 Day of competition
- **What:** Checked the time column for drops.
- **Finding:** Each 2-day Czech sheet has exactly **one** clear drop in time of day (evening → morning), so day 1 and day 2 can be told apart reliably. EFC days come from the sheet name.
- **Why:** needed to join hourly weather on the correct date.

### 0.4 Data-quality issues found (to be handled in Step 1)
- **Fault codes:** inconsistent spelling (`ok/OK/Ok`). Codes appear in the wrong columns (e.g. `vběhl` in a changeover column, `ok`/`chyba` in a run column). Some run times are negative.
- **Incomplete rows:** heats with fewer than 4 dogs, zero totals and missing outcomes.
- **Extreme values:** totals up to 86 s, runs up to 73 s, changeovers up to 46 s, starts up to 25 s.
- **Placeholder dog names:** Chase, Rubble, Zuma and Marshall are reused across unrelated teams. Some opponent dog names collide with WRFT names (Abby, Easy, Scotty).
- **Master data:** 4 ulna entry errors, inconsistent breed spellings, birth dates stored as Excel serial numbers.
- **Dates:** the Czech championship is dated "3–4 September 2023" (Sun–Mon), while every other competition runs Sat–Sun. To verify.
- **Venues:** several venue names are ambiguous (Heroltice, Louňovice, Pláně).

### 0.5 Domain checks (details in `domain_knowledge.md`)
- **Jump heights vs. FCI ulna table**
  - **What:** Compared each dog's recorded jump height with the FCI table, after correcting the 4 obvious ulna entry errors (×10 or ÷10).
  - **Result:** 49/51 match. The 2 mismatches (Punk, Hank) are within 0.03 cm of a band limit.
  - **Why:** confirms the competitions follow FCI rules and that the 4 corrections are right.
- **Total time identity**
  - **What:** Tested `total = start + Σruns + Σchangeovers` on the 6,286 fully numeric rows (`ok` = 0).
  - **Result:** 87.7 % match within ±0.02 s. The rest have extra time from reruns.
  - **Why:** gives a way to detect reruns and a reason to use clean time as the speed metric.
- **Negative starts vs. outcome**
  - **Result:** with a negative start and no rerun time, 494/510 heats (97 %) were lost.
  - **Why:** consistent with the rule that an uncorrected fault invalidates the heat. It also confirms the meaning of negative starts.

### 0.6 Sources
- **Hungarian rulebook:** the link in the brief is dead (403/404, no archive copy).
- **UKFL PDF:** the link has a typo (`1-o` instead of `1-0`); the corrected URL works.
- **Supplementary source:** the FCI Regulations for Flyball Competitions (2023 annex), which match the data.
- Full list in `domain_knowledge.md` §0.

### 0.7 Documentation created
- `data_structure.md`: physical layout of the Excel files, the font-colour encodings, per-sheet facts (row counts, WRFT teams, day breaks) and anomalies.
- `domain_knowledge.md`: domain rules and their implications for the analysis.
- `CLAUDE.md`: project guide and current status, so a new working session can continue without this conversation's context.

---

## Step 1 – Data cleaning (Phase 2, started 2026-10-13)

The source Excel files are only read, never changed. All logic lives in `src/flyball/`; `scripts/run_phase2_clean.py` rebuilds every output.

### 1.0 Environment
- **What:** Created a `uv` project (`pyproject.toml`, `uv.lock`, `.venv`) with the package in `src/flyball/`. Installed pandas 3.0, numpy, openpyxl, pyarrow, scipy, statsmodels, matplotlib, seaborn, requests, jupyter, nbconvert and pytest.
- **Why:** reproducible environment; the notebooks import the same code as the scripts.

### 1.1 Reading the competition sheets (`excel_reader.py`)
- **What:** openpyxl reader. Reads columns A–T **by position**, because the headers repeat. Font colours are converted to RGB through each file's own colour palette, so one rule works for both files:
  - red team-name font = red lane; blue = blue lane
  - red font on a time cell = fault marker
- **Finding: a blank row inside two sheets.** `Eager´s Cup 1` and `Eager´s Cup 2` each have **one empty separator row at the day break** (Excel rows 315 and 332). A "stop at the first empty row" rule would silently lose day 2 (329 + 376 rows).
  - **Rule:** skip blank rows and stop only after 20 blank rows in a row.
- **Result:**
  - 8,571 data rows and 1,128 WRFT rows, exactly as in Step 0.
  - Every row has a lane colour: 4,290 red, 4,281 blue.

### 1.2 Titles and competition days (`parse.py`)
- **What:** Parsed the B1 title into competition, ring, venue and dates (Hungarian month names). For 2-day sheets, the day is split at the single drop in time of day. The code **checks** that there is exactly one drop and fails loudly otherwise. EFC sheets have one date each in the title.
- **Result:**
  - 16 sheets, 11 competitions, 28 sheet-days (12 CZ sheets × 2 days + 4 EFC sheets).
  - The day-2 start positions match `data_structure.md` §3 for all 12 CZ sheets.
- **Note:** openpyxl returns the CZ time cells as clock times and the EFC cells (stored as 1 + fraction) as datetimes on 1899-12-31. Only the clock part is used.

### 1.3 Time-cell codes (`parse.py: classify_time`)
- **What:** Every start, run and changeover cell becomes a number in seconds (rounded to 3 decimals) plus a code:
  - `ok/OK/Ok` → 0.00 s pass
  - `chyba/error` → unquantified early pass
  - `mimo/outside` → missed hurdle
  - `vběhl/run in` → ran in
  - negative start → false start
  - negative changeover → early pass
  - negative run → invalid
- **Why:** the brief defines these codes; all spellings found in the data are mapped (Step 0 inventory). No other text appears in any time cell.

### 1.4 Shifted rows after a "ran in" code (`parse.py: realign_shifted_row`)
- **Finding:** in **19 rows**, a `vběhl` (ran in) code sits in a dog's **changeover** cell instead of its run cell, and **every later value in the row is one cell too early**. Example, Křupky row 109:
  - recorded: `chg2 = vběhl, run2 = -0.10, chg3 = 5.13, run3 = OK, chg4 = 5.36`
  - realigned: `chg2 = –, run2 = vběhl, chg3 = -0.10, run3 = 5.13, chg4 = OK, run4 = 5.36`
- **Evidence the realignment is right:**
  1. This one pattern accounts for **all 13 negative run times** and **all 3 `ok`/`chyba` codes found in run cells**. After realignment, no code is in the wrong kind of cell and no run time is negative.
  2. In the 7 realigned rows where only the run-in dog's time is unknown and nobody re-ran, `total − all known parts` gives that dog **4.1–5.2 s**, a normal single-dog time. Larger leftovers occur only in rows with reruns.
- **Rule:** move the code to the run cell, leave that dog's changeover empty, and shift the later values one cell right. The value pushed off the end (10 rows) is kept in `overflow_value` but not used. Rows are flagged `row_realigned`.

### 1.5 Dog master data (`dogs.py`)
- **What:**
  - Read 51 dogs and renamed the columns to English.
  - Birth dates: pandas converts the date-formatted serial numbers correctly. Serial 40223 is **2010-02-14**; the example in `data_structure.md` said 02-15, an off-by-one slip that has been corrected there.
  - Ulna: fixed the 4 entry errors: Speedy 1.491 → 14.91, Henry 1.209 → 12.09, Bruno 175.5 → 17.55, Falco 152.8 → 15.28.
  - Added `breed_group`: Border Collie 26 (4 spellings), Mix 8 (`Mix` + `Keverék`), Other 17.
  - Added `category` (sex × neutered): neutered male 22, neutered female 19, intact male 8, intact female 2.
  - Added `jump_height_fci` as a check.
- **Result:** the recorded jump height matches the FCI table for 49/51 dogs. Punk and Hank sit on a band edge, as in Step 0. The recorded height stays authoritative.
- **Flag for validation:** the youngest dog was born on 2022-05-02 and reaches 18 months only on 2023-11-02, after the season. It is checked in Step 1.9.

### 1.6 Heats and races (`clean.py: pair_heats, assign_races`)
- **What:** Two consecutive rows with the same clock time and swapped teams form one **heat**. Consecutive heats of the same two teams within a sheet-day form a **race**.
- **Result:**
  - 4,235 paired heats (8,470 rows) + 101 unpaired rows = **4,336 heats** in **1,172 races**.
  - **Every paired heat has one red and one blue team.** This is an independent confirmation that the font colour is the lane.
  - No paired heat has two winners.
- **Unpaired rows (101):** they are kept as heats of their own (`paired = False`). They come in two kinds:
  - practice rows (see 1.7)
  - real heats whose opponent row is simply missing from the sheet, e.g. most of Fire-Drakes' and Hop Trop PRAGUE's races
  - Their dog times are real, so they stay usable for dog-level analysis.
- **Loss/loss heats:** both teams lost in 439 paired heats. This is allowed: an uncorrected fault means "no time".
  - 414 of them contain a fault.
  - 15 are complete and fault-free, all in lower divisions. These are most likely **break-outs**, where a team ran faster than the division limit and so lost the heat (FCI 2.05j). That is the only legal way a clean heat is lost.

### 1.7 Heat-level metrics and flags (`clean.py: flag_heats`)
Flags only, no rows deleted.

**Metrics:**
- `clean_time` = sum of the 4 run times, only when all 4 are clean numbers (FCI "clean time").
- `rerun_time` = total − (start + 4 runs + 3 changeovers). Computed only when all 8 parts are numeric; `ok` counts as 0, and negative starts and passes are included.
- **Identity tolerance changed to ±0.04 s** (Step 0 used ±0.02). Every part is displayed to 0.01 s, so 8 rounded parts can be off by up to 8 × 0.005 = 0.04 s; the residuals indeed fall on a 0.01 s grid.
  - Result: **5,588 of 6,286 rows (88.9 %)** satisfy the identity. Step 0 reported 87.7 % because of the tighter tolerance.
  - 696 rows have rerun time (`has_rerun`). Only 2 rows are more than 0.04 s *below* their parts (−0.05 and −0.10 s); this is ignored.
- Fault counts per row: false start, pass faults (negative changeover or `chyba/error`), run faults (`mimo/outside`, `vběhl/run in`).

| Flag | Rows | Rule / reason |
|---|---|---|
| `is_practice` | 28 | No result, at most 1 dog ran, total ≤ 8 s. A practice start before the first heat (FCI 2.05d). Totals 0–7 s |
| `no_outcome` | 107 | Result cell empty. Includes the 28 practice rows. The rest are full or partial heats without a recorded result; their dog times are kept |
| `is_zero_total` | 17 | Total = 0 (heat abandoned after a fault) |
| `has_placeholder_dog0` | 14 | Dog name is the number `0` (Budějckej 2 and others). These slots get no dog key |
| `is_complete` | 7,670 | 4 dog names and all 8 time cells filled |
| `is_clean_heat` | 5,242 | Complete and no fault of any kind |

- **Partial heats are normal:** 180 rows have a result but fewer than 4 dogs, because once the heat is decided the losing team often stops. They are not errors and are not excluded.
- **Red-font cross-check:** every fault-like value (negative time or fault text) is in red font; there are 0 exceptions. There are 616 mismatches in the other direction: 615 are **empty** cells formatted red, which carry no information, and 1 is an `ok` in red (Eager's Cup 1, row 156). The check counts non-empty cells only.

### 1.8 Dog slots, dog keys and outlier rules (`clean.py: build_runs, flag_runs`)
- **What:** Each heat row is split into its 4 dog slots, giving **33,904 slots**. A slot is kept if it has a name or any run value.
  - The pass belonging to position 1 is the start; for positions 2–4 it is that dog's changeover.
  - `prev_dog_key` and `next_dog_key` give the dog before and after in the same row, with their sex × neutered category for WRFT rows. This covers both readings of Question 2.
  - **Dog key:** WRFT rows use the master-data name; there are **0 unknown names** and **50 of 51 dogs** appear (Fibo never ran). Other teams use `team|name`, because opponents reuse names (Chase, Zuma, Abby…) and nothing reliably links dogs across opponent teams.
- **Outlier rules.** Each rule is a separate flag, so later phases can test the effect of each one.

| Flag | Slots | Rule | Why |
|---|---|---|---|
| `run_fault` | 540 | run cell is `outside` or `run in` | faulted run, no time |
| `run_too_fast` | 16 | run < 3.3 s (values 0.007–3.27) | the fastest dog ever recorded ran 3.383 s |
| `run_over_ceiling` | 23 | run > 10 s | 31 m in 10 s is a trot; the 99.9th percentile is 9.1 s; these are stops or interruptions, not speed |
| `run_dog_outlier` | 249 | > max(5 × the dog's robust spread, **1.0 s**) slower than the dog's own median, for dogs with ≥ 10 runs | catches stumbles and ball bobbles for dogs whose runs are otherwise very consistent |
| `pass_over_ceiling` | 213 | start or changeover > 3 s | the dog was held back, not passed (99.5th percentile of starts is 0.8 s; 99th of changeovers is 2.6 s) |

- **Per-dog rule tuning:** dogs are very consistent (median spread 0.09 s). A pure "5 × spread" rule would flag 484 runs only ~0.5 s slower than usual, which is genuine variation that weather or lane analyses should keep. The extra 1.0 s floor cuts this to 249 runs, 0.8 % of clean runs.
- **`valid_speed`** = clean numeric run ∧ not practice ∧ none of the run flags above. This gives **32,967 slots**.
- **`valid_pass`** = numeric or `ok` pass ∧ not practice ∧ ≤ 3 s. This gives **29,809 slots**.
- Runs whose *pass* was faulted (early pass) keep `valid_speed`; the `pass_fault` flag lets Phase 3 test them separately.

### 1.9 Validation checks (`clean.py: validate, hurdle_by_dog`)

**Czech championship date:**
- **Finding:** the sheet title says 3–4 Sep 2023 (Sun–Mon).
- **Evidence:** the Hop Trop club results page (https://www.hoptropflyball.cz/uspechy-2/) lists the event as **Mistrovství ČR, Blšany, 2–3 Sep 2023**. Its best times match our sheet **exactly**:
  - Hop Trop PRAGUE 16.38 s (div 1) and HURRICANE 17.82 s (div 2).
  - The same page's Flyvaryors tournament times (16.92 s and 17.48 s) also match our data.
- **Action:** dates corrected to **2–3 Sep 2023 (Sat–Sun)** via `config.DATE_OVERRIDES`. The title date is kept in `competitions.csv` (`date_from_title`). This matters for the weather join.

**Hurdle height vs. the smallest WRFT dog:**
- **Finding:** in 204 of 1,128 WRFT rows (18 %), the recorded hurdle differs from the master jump height of the smallest dog that ran: 112 lower and 92 higher.
- **Pattern** (`wrft_hurdle_check.csv`): the differences are **systematic per dog, not random**.
  - Always **one step (2.5 cm) lower** than the master height whenever that dog sets the hurdle: Alfie 35/35 rows, Maggie 36/36 and Moon 28/28 (master 30, raced at 27.5); Bonnie 65/65 (master 27.5, raced at 25); Brooke and Bree 4/4.
  - Higher than needed: Henry 12/12 at the EFC (master 20, raced at 25); Pax 61 of 138 rows.
  - 22 other height dogs match perfectly.
- **Interpretation:** the master sheet probably records some dogs' current measurement rather than their official 2023 height (a lower hurdle than allowed would lose the heat, so it is unlikely to be a rule breach).
- **Action:** the **recorded heat hurdle stays authoritative**. Phase 4e (line-up) should use each dog's height as raced in 2023.

**Age:**
- **Finding:** **Hank** (born 2022-05-02) and **Bonnie** (born 2022-03-08) were 11.7–17.4 and 13.5–15.8 months old when they raced, while FCI requires 18 months. Hank appears in 166 slots and Bonnie in 105.
- **Interpretation:** either their birth dates in the master data are wrong, or the masking shifted them. No change made.
- **Note for Q2:** Bonnie is one of only 2 intact females, so the intact-female group is even thinner and younger than it looks.

**Other checks:**
- Two WRFT teams on the same day: only **Abby**, at Crazy Cup on both days (XXL and Zephyr). This is reported only, since FCI has no such rule.
- No dog appears twice in one row.
- No WRFT row is missing its hurdle.

### 1.10 Spot-check, tests and outputs
- **Spot-check** (`flyball.spotcheck.compare`, notebook §9): raw cells were re-read straight from the Excel with openpyxl, independently of the pipeline, and compared value by value.
  - **Hanácké row 3** (WRFT vs WRFT): false start −0.24 with no rerun, recorded as a loss. ✔
  - **EFC_2 ring_1 row 3** (English `error` code, `1 + fraction` clock). ✔
  - **Crazy Cup row 137** (WRFT XXL): false start, 9.95 s rerun time. ✔
  - **Eager's Cup 1 row 3:** practice row, flagged, with no heat number. ✔
  - **Křupky row 109:** realigned as in 1.4. ✔
  - **Budějckej 2 row 3:** dog name `0` and empty hurdle, kept with the placeholder flag; its total (3.95 s) is smaller than its first dog's run (4.35 s), so the row is internally inconsistent. ✔
  - All values match.
- **Tests** (`uv run pytest`): 62 pass.
  - Parser unit tests: codes, titles, day split, realignment, breed groups, FCI table.
  - Invariants: 8,571 / 1,128 rows; per-sheet row, WRFT and day-2 counts; lanes 45–55 % red per sheet and one red + one blue per heat; identity 88.9 % of 6,286; codes only in the right cells; 50 WRFT dogs and 0 unknown; 4 ulna fixes; only Saturday/Sunday dates.
- **Outputs** in `data/processed/` (not in git; rebuilt in ~3 s by `scripts/run_phase2_clean.py`): `competitions.csv`, `heats.parquet`, `runs.parquet`, `dogs.csv`, `data_quality.csv`, `wrft_hurdle_check.csv`.
- **Notebook:** `notebooks/02_cleaning.ipynb` gives the plain-language walk-through with the evidence for every rule. It is executed with `nbconvert --execute`.

---

## Step 2 – Basic analyses (Phase 3, 2026-10-13)

Nothing in the processed tables is changed. Phase 3 only reads `data/processed/` and writes results to `reports/phase3/`, `reports/dog_scorecards.csv` and `figures/phase3/`. `scripts/run_phase3_basic.py` rebuilds all of them in about 15 s. `notebooks/03_basic.ipynb` is the plain-language walk-through. Code: `metrics.py` (tables), `stats.py` (models), `plots/` (draft charts).

### 2.1 Analysis base and conventions
- **Practice rows dropped** on load (28 rows). This leaves 8,543 team rows (1,123 WRFT) and the dog slots of those rows.
- **Peer group = competition × division** (`comp_div`).
  - **Why:** division numbers are set per competition (Div 1 at the EFC is not Div 1 at Křupky), and WRFT teams moved between divisions (Maximini ran in divisions 1–8).
  - Each `comp_div` group has 4–14 teams and never spans two rings.
  - Only 15 of 378 team × competition combinations changed division within a competition.
- **Outcomes:**
  - 8,452 decided team rows (win or loss) + 12 ties + 79 rows without a result.
  - Ties count as ½ in win rates and are left out of the win models.
- **Speed metric:** `clean_time` = the sum of the 4 run times when all 4 runs are clean numbers. Start or pass faults don't change run times, so those heats keep their clean time.
- **Clean heat:** all 4 dogs ran, no coded fault, and no rerun time (`has_rerun`).
  - **Finding:** 459 decided team rows (282 lost, 177 won) have rerun time but **no coded fault**. These are faults the sheets don't record, such as a dropped ball, so they are not counted as clean.
- **Team "typical" strength on a day:** a **leave-one-out** median over the team's *other* heats that day. It is used for clean time, start and clean total, so a heat's own result doesn't leak into its predictors.

### 2.2 Finding: `ok` is a censored pass value
- **What:** looked at the distribution of numeric pass times.
- **Finding:**
  - Numeric passes between 0.00 and 0.07 s almost never occur: 19 values among the 22,437 numeric or `ok` passes at positions 2–4. Above that, the count rises smoothly from 0.08 s and peaks at 0.15 s.
  - `ok` makes up 34 % of passes, and dogs whose numeric passes are tighter get more `ok`s (correlation −0.53 over dogs with ≥ 30 passes).
  - `ok` is unrelated to lane (34.2 % blue vs 33.9 % red) and is spread over rows as expected by chance.
- **Interpretation:** `ok` means "a tight pass, under about 0.08 s, value not displayed". It is not an exact 0.00.
- **Rule:**
  - **Medians** treat `ok` as 0, which is correct because it is the smallest value.
  - **Means** use 0.04 s, the middle of the range (`metrics.OK_PASS_IMPUTE`).
  - The `ok` share is reported separately for each team and dog.

### 2.3 What wins a heat (defining a "good result")
- **Win rate by fault status** (`win_by_fault_status`, 8,376 team-heats, both sides of every paired heat):

| Own heat | Opponent heat | Win rate (95 % CI) |
|---|---|---|
| clean | clean | 49.3 % (47.6–50.9) |
| clean | fault | 85.0 % (83.3–86.5) |
| fault | fault | 19.1 % (16.8–21.8) |
| fault | clean | 8.9 % (7.7–10.2) |

- **In clean-vs-clean heats** (`win_by_speed_gap`), the win rate falls steadily with the gap in typical clean time:
  - 75–85 % when typically 0.5–1.5 s faster;
  - 62 % when 0–0.5 s faster;
  - 37 % when 0–0.5 s slower;
  - 14–23 % when 0.5–1.5 s slower.
- **Heat-win model** (`stats.heat_win_models`):
  - **Design:** logistic regression, one row per decided paired heat seen from a focal team (the first row of the pair; for the WRFT fit, the WRFT team). Predictors are the speed gap and start gap (typical, leave-one-out) and each side's faults (false start, pass fault, run fault).
  - **Standard errors:** cluster-robust on **race**.
    - **Change from plan.md:** the plan named a logistic model with a team random effect. statsmodels has no frequentist mixed logistic model, and plan.md's standards allow cluster-robust models.
    - Race is the clustering unit instead of team, because each heat involves two teams and the WRFT sample has only 7 teams (too few clusters).
  - **Results:** speed only, faults only and the full model are compared on the same heats (4,146 field heats, 1,000 WRFT heats):

| Sample | Speed only R² / AUC | Faults only R² / AUC | Full R² / AUC |
|---|---|---|---|
| Field | 0.017 / 0.60 | 0.249 / 0.81 | 0.266 / 0.84 |
| WRFT | 0.035 / 0.65 | 0.218 / 0.80 | 0.258 / 0.84 |

  (R² = McFadden pseudo-R².)
  - **Field odds ratios** (full model): own false start 0.069, own pass fault 0.062, own run fault 0.31; 0.66 per second of typical speed disadvantage; start gap not significant (p = 0.21).
  - **WRFT odds ratios:** 0.13, 0.11, 0.08 for the three fault types, and 0.67 per second.
- **Definition adopted:** a good result is a **won heat**. Its levers, in order of weight, are (1) a clean heat and (2) a faster clean time than the division peers.

### 2.4 Why heats are lost (`fault_attribution`)
- **Rule:** every decided row is labelled, in this order of priority:

| Label | Condition |
|---|---|
| `win_clean` | won, no fault, no rerun |
| `win_after_fault` | won with a fault or rerun time |
| `loss_fault` | lost, with a coded fault |
| `loss_uncoded_rerun` | lost, rerun time but no coded fault |
| `loss_breakout_like` | lost, complete and clean, and the opponent also lost |
| `loss_slower` | lost, complete and clean |
| `loss_not_finished` | lost, not all dogs ran, no coded fault |

- **Avoidable loss:** a `loss_fault` against a winning opponent where the team's typical clean total that day (leave-one-out median of its clean totals) is below the opponent's total.
- **Result (WRFT, 1,114 decided rows):**

| Reason | Heats |
|---|---|
| won clean | 376 |
| won despite a fault | 78 |
| lost with own fault | 376 |
| lost, uncoded rerun | 34 |
| lost clean but slower | 220 |
| lost, break-out-like | 16 |
| lost, not finished | 14 |

  - **62.1 % of WRFT losses involve its own fault** (field: 61.0 %).
  - **155 WRFT losses (23.5 %) are avoidable** (field: 23.8 %). They involve early passes in 99, false starts in 58 and run faults in 20 (a heat can have more than one).
  - Avoidable losses by team: Zephyr 38, Hopefuls 34, Maximini 31, Nightfall 21, Dreamers 19, Wonders 7, XXL 5.
- **Cost of a single fault** (`fault_cost_seconds`, heats with exactly one fault):

| Fault | Heats | Loss rate | Corrected (rerun time known) | Median rerun time |
|---|---|---|---|---|
| False start | 637 | 86.2 % | 141 | 7.76 s |
| Pass fault | 1,369 | 88.8 % | 79 | 8.33 s |
| Run fault | 316 | 69.3 % | – | – (a faulted run has no time, so the rerun cost can't be computed) |
| Clean heats | 4,752 | 33.6 % | – | – |

### 2.5 Team level
- **`team_summary`:** for each team, win rate (Wilson CI), clean-heat rate, median and best clean time, heat-level fault rates by type, rerun seconds per heat, median start, median pass, `ok` share, pass-level early-pass rate and median run. WRFT overall vs the field:
  - win rate 40.8 % vs 45.6 %;
  - clean heats 54.4 % vs 56.6 %;
  - **false-start heats 15.8 % vs 10.6 %**;
  - median pass 0.20 s vs 0.15 s, with a lower `ok` share (27.6 % vs 35.1 %);
  - median run 4.28 s vs 4.27 s.
- **`peer_benchmark`:**
  - **Method:** each WRFT team against the other teams of the competition × divisions it raced in. OLS `metric ~ focal + C(comp_div)`, with standard errors clustered on team (a linear probability model for rates).
  - 6 metrics × 7 teams = 42 tests, **Holm-adjusted**.
  - **Significant after Holm** (team − peers):
    - **Nightfall:** clean time −0.42 s; win rate +9.4 points; false starts +5.5 points.
    - **Dreamers:** clean heats +9.0 points; false starts +3.7 points; run faults −2.4 points.
    - **Hopefuls:** early passes +5.8 points; false starts +3.0 points.
    - **Maximini:** clean time +0.40 s; win rate −7.3 points; clean heats −7.6 points.
    - **Zephyr:** run faults +7.9 points.
    - **XXL:** clean time +2.43 s; win rate −15 points; **false starts +20.0 points**.
    - **Wonders:** clean time +2.20 s; win rate −24 points; clean heats −20 points; run faults +5.0 points.
- **`division_ranks`:** the rank of each WRFT team's median clean time within each comp_div.
  - Nightfall ranked first in 3 of 7 divisions.
  - Wonders and XXL sat a median of 2.15 s and 1.96 s behind their division medians.

### 2.6 Starts and passes (`pass_profile`, `pass_window`)
- **Method:** a dog-level comparison over all dogs with ≥ 20 attempts (120 starters and 335 passers in the field). Dogs are grouped by their median start or pass time, and the pooled fault rate (Wilson CI) and expected cost are compared across groups.
  - Expected cost = mean time on the line + fault rate × the median rerun time from 2.4.
  - Held passes over 3 s are excluded from the time part.
- **Passes:** the early-pass rate falls as the median pass gets looser:
  - 10.9 % (median ≤ 0.08 s) and 10.5 % (0.08–0.12 s);
  - 8.9–9.2 % (0.12–0.20 s);
  - 7.2 % (0.20–0.25 s);
  - 5.7 % (0.25–0.35 s);
  - 3.4 % (> 0.35 s).

  The expected cost is lowest at 0.25–0.35 s (0.84 s per pass), but the whole 0.12–0.35 s range sits within 0.84–0.99 s. Passing tighter than 0.12 s costs the most (1.02–1.03 s).
- **Starts:** the opposite pattern. Dogs with a median start of 0.05–0.08 s have the lowest false-start rate (8.3 %, 39 dogs). Slow starters (0.14–0.18 s) have the highest (15.7 %). Starting is a skill rather than a risk trade-off.
- **Caveat:** this is a between-dog comparison, so it is descriptive (better handlers may be both quicker and safer).

### 2.7 Dog level
- **`dog_scorecard`** (`reports/dog_scorecards.csv`, 50 dogs):
  - slots; valid runs; median run, 5th-percentile best and MAD;
  - usual hurdle and position;
  - starts, false starts and median start;
  - passes, early passes, median pass and `ok` share;
  - run faults.
- **Rates** carry Wilson CIs and an **empirical-Bayes** shrunken value (`*_eb`, NaN when a dog has no attempts).
  - **Method:** a beta-binomial prior fitted by maximum likelihood.
  - **Fix during the phase:** a first method-of-moments fit gave every dog the same early-pass value (0.091). Dogs with only a few passes inflated the noise term until the between-dog variance came out as zero. The maximum-likelihood fit gives sensible shrinkage, e.g. Kent's run faults move from 5/9 to 0.21.
- **`adj_run_s`:** the dog's random effect from the run-time model, at position 1, a 25 cm hurdle and an average day.
- **Correction to the plan's note:** the 15 cm height dog WRFT actually raced with is **Gordon** (115 valid runs, median 6.92 s). Punk has only 5 runs. 116 WRFT rows were run at 15 cm (Wonders, XXL and Zephyr).
- **Run-time model** (`stats.dog_run_model`):
  - **Model:** MixedLM `log(run_time) ~ C(position) + hurdle_step + C(comp_day_id) + (1|dog)` on `valid_speed` runs (hurdle_step = (hurdle − 25 cm) / 2.5).
  - **Robustness check:** OLS with dog fixed effects and dog-clustered errors.
  - **Field** (32,777 runs, 903 dogs), per run:
    - positions 2 / 3 / 4 are +0.80 % / +0.78 % / +1.00 % slower than position 1 (+0.034 / 0.033 / 0.043 s);
    - each 2.5 cm hurdle step adds **+0.46 % (0.020 s, CI 0.018–0.022)**;
    - the fixed-effects model agrees within 0.03 percentage points.
  - **WRFT** (4,340 runs, 50 dogs): positions +0.90 / +0.61 / +0.87 %; hurdle +0.34 % per step. Same direction as the field, but with wide CIs in the dog-clustered fixed-effects model (50 clusters).

### 2.8 Sensitivity checks (`metrics.sensitivity` + notebook §6)

| Check | Effect |
|---|---|
| WRFT win rate (baseline 40.8 %): drop WRFT-vs-WRFT heats | 39.1 % (−1.7 points) |
| WRFT win rate: drop ties | −0.02 points |
| WRFT win rate: paired heats only | −0.3 points |
| Keep per-dog outlier runs | WRFT dog medians unchanged for the typical dog; max change 0.03 s |
| Keep held passes over 3 s | WRFT pass medians unchanged for the typical dog; max change 4.16 s for one dog (the reason the rule exists) |
| Heat-win model without loss/loss heats | pseudo-R² speed 0.024, faults 0.281, full 0.305; the conclusion stands |

### 2.9 Checks, tests and outputs
- **Spot-check against the raw Excel** (openpyxl values, independent of the pipeline):
  - Nightfall: 153 decided heats, win rate 0.5359, median clean time 17.360 s from 143 heats. Matches `team_summary`. ✔
  - Cookies: 51 starts, 19 false starts. Matches the scorecard. ✔
  - An avoidable loss, Hanácké škvarek row 11: Hopefuls ran 16.27 s with an uncorrected `chyba` early pass and lost to FOFR DOG's 18.43 s. Their typical clean total that day was 16.40 s. ✔
- **Tests:** `uv run pytest` gives **74 passed** (62 earlier + 12 new in `tests/test_metrics.py`):
  - helper tests: Wilson CI, EB shrinkage, Holm, AUC, leave-one-out median;
  - hand-built fault-attribution and avoidable-loss cases;
  - real-data invariants: no practice rows, ties = ½, attribution covers each decided row once, the heat view pairs opponents, 50 scorecards with rates in [0, 1], pass-window groups partition the dogs.
- **Outputs:**
  - `reports/phase3/`: `team_summary`, `peer_benchmark`, `division_ranks`, `fault_attribution`, `fault_cost`, `win_by_fault_status`, `win_by_speed_gap`, `heat_win_model`, `heat_win_model_fit`, `pass_window`, `dog_effects`, `sensitivity` (all CSV);
  - `reports/dog_scorecards.csv`;
  - `figures/phase3/`: `heat_outcomes`, `what_wins`, `team_quadrant`, `pass_window`, `dog_quadrant`, `dog_effects` (PNG drafts, built with the dataviz skill; palette validated, with red and blue kept for lanes).

---

## Step 3 – Weather data (Phase 4.0, 2026-10-13)

**Goal:** attach historical weather to every competition day and every heat. This step only fetches and joins the data; the weather *analysis* is Phase 4B. Code: `src/flyball/weather.py`, `scripts/run_phase4_weather.py`; notebook `notebooks/04_0_weather.ipynb`.

### 3.1 Venues (`config.VENUES`)
- **What:** fixed coordinates for the 10 venues named in the sheet titles. Coordinates come from the Open-Meteo geocoder. Each entry carries a note and a source URL.
- **Ambiguous names, resolved from the competitions' own pages:**
  - **Heroltice:** 4 villages share the name. We picked **Heroltice, Brno-venkov** (near Tišnov). The flyball.cz location page lists the "Happy Herolky" dog-sport ground at Heroltice 65, and a Brno club's 2023 race report calls the event "on our doorstep".
  - **Louňovice:** 2 candidates. We picked **Louňovice, Praha-východ** (near Mukařov), which is what the flyball.cz event page "Máchale, spadlo ti to! 2023" gives. Not Louňovice pod Blaníkem.
  - **Pláně:** several candidates. We picked **Pláně, Plzeň-sever**, the airfield near Plzeň where M.E.D.'s Trophy is held (flyball.cz 2022 event page, plus a 2018 club report).
  - **Blšany:** also ambiguous, which we only noticed while checking. We picked the **football ground at U Stadionu 10, 439 88 Blšany**, Louny district; flyball.cz and the Flyvaryors propositions say it is a grass pitch. Not Blšany u Loun. Both Blšany events (May and the Czech championship in September) are at this venue.
  - **Vodňany:** the sheet title says Vodňany, while flyball.cz files Budějckej xtreme under České Budějovice, about 25 km away. We kept the title venue; at this distance the weather is practically the same.
- **Why:** the weather must come from the right place. All picks are documented, so they can be audited or changed in one place.

### 3.2 Fetching (`weather.fetch_plan`, `fetch_venue`)
- **What:** **11 requests** to the Open-Meteo historical archive (`archive-api.open-meteo.com/v1/archive`), one per event. Each request covers the event days **plus the day before**. It asks for these hourly variables:
  - temperature and apparent temperature
  - relative humidity and dew point
  - cloud cover
  - wind speed, wind direction and gusts (m/s)
  - precipitation and rain
  - shortwave radiation

  Times are in local time (Europe/Prague or Europe/Budapest, CEST in season), which matches the local clock in `heat_time`. The Czech championship uses the corrected dates (2–3 Sep, Step 1.9).
- **Coverage:** 28 sheet-days map to **22 venue-days**, because 2 rings at the same venue share the same weather. The output has **792 hourly rows** (11 × 72 h).
- **Cache:** the raw JSON responses are stored in `data/external/weather/` (136 KB). This folder is **committed to git** as an exception to the ignore rule, because reanalysis data can be revised later and the deliverable should rebuild offline with exactly the same numbers. Use `--refresh` to re-download.
- **Model grid:** Open-Meteo answers for its nearest grid point (default `best_match` model, about 10 km grid). Each venue is **0.9–6.7 km** from its grid point (`weather.grid_points`).
- **Why:** this source is free, has no key, and is consistent across all 10 venues. There are no stations at the dog grounds.

### 3.3 Joining weather to heats (`weather.heat_weather`, `day_weather`, `attach`)
- **Per heat**, at the minute it ran:
  - **Instantaneous values** (temperature, humidity, dew point, cloud, wind speed) are interpolated linearly between the two surrounding full hours.
  - **Wind direction** is interpolated as a vector, so 350° and 10° give 0°, not 180°.
  - **Hourly totals and maxima** (rain, gusts, radiation) are taken from the hour block that contains the heat. In Open-Meteo these are reported at the *end* of the hour, so a heat at 10:30 gets the value stamped 11:00.
  - **Wet ground:** `precip_3h_mm` and `precip_24h_mm` are the rain in the last 3 and 24 hour blocks.
  - **Result:** **4,336 of 4,336 heats** matched, with no gaps. Practice heats are included; the analysis filters them. `weather.attach()` adds the columns to the heats or runs tables by `heat_id`; tested on all 33,904 run slots, with 0 unmatched.
- **Per sheet-day**, over the racing window (the full hour before the first heat to the full hour after the last):
  - temperature min, mean and max, and apparent maximum
  - mean humidity, dew point and cloud
  - mean radiation
  - mean wind and maximum gust
  - total rain and rain hours (≥ 0.1 mm)
  - rain in the 24 h before racing
- **Outputs:** `data/processed/weather_hourly.csv`, `weather_day.csv`, `heat_weather.parquet`; draft figure `figures/phase4/weather_strip.png`.

### 3.4 Checks and what the data shows
- **Spot-check against independent station records** (Meteostat hourly, nearest synoptic station, racing hours 08–18). This was a one-off check and is not part of the pipeline:

  | Venue (station, distance) | Hourly temperature r | Mean abs. difference | Daily max, model vs station |
  |---|---|---|---|
  | Heroltice (Brno-Tuřany, 27 km) | 0.94 | 1.3 °C | 19.5/19.7, 18.2/19.6 |
  | Louňovice (Praha-Ruzyně, 38 km) | 0.93 | 1.8 °C | 33.5/35.2, 28.4/27.0 |
  | Vodňany (Temelín, 13 km) | 0.98 | 1.1 °C | 19.7/19.8, 10.6/8.9 |
  | Tápiószentmárton (Budapest airport, 44 km) | 0.97 | 0.6 °C | 31.0/30.7, 24.7/25.4 |

  - **Humidity:** within about 5 points on 5 of 8 days, but up to 16 points off (Heroltice 23 Apr: 64 % vs 48 %; Louňovice 16 Jul: 56 % vs 69 %).
  - **Mean wind:** within about 1 m/s on most days, up to 2 m/s off. Station wind is measured at open airfields, so some difference is expected.
  - **Rain disagrees on showery days.** For example, the model gives 2.6 mm at Vodňany on 14 Oct against 0 at Temelín, and 4.5 vs 2.5 mm at EFC on 30 Jul. Showers are local and the model smears light rain, so rain should be used as a **dry/wet indicator**, not as exact millimetres.
  - A qualitative check also agrees: the Brno club called Heroltice's weather "super", and the model shows dry, 15–19 °C days.
- **Tests:** 10 new tests in `tests/test_weather.py`, **84 in total**, all passing.
  - Hand-built cases: interpolation, wind-direction wrap, hour-block rule, refusal of heats outside the fetched hours.
  - Real-data invariants:
    - every venue has coordinates
    - 28 sheet-days map to 22 venue-days, and rings on the same day get identical weather
    - every heat is matched
    - values are in plausible ranges
    - the daily temperature peak falls in the afternoon, which confirms the time zone
- **Season picture (for 4B):**
  - **Temperature:** racing temperatures range from about **7 °C** (Vodňany, 15 Oct, after an overnight cold front) to **33.5 °C** (Louňovice, 15 Jul, heatwave).
  - **Rain:** never heavy during racing (at most 4.5 mm over a day).
  - **Wind:** mean 1.4–5.7 m/s, gusts up to 14.5 m/s.
  - **Saturday vs Sunday:** 4 events changed sharply between the two days (Žamberk, Louňovice, EFC, Vodňany), which helps separate weather from venue.
- **Limitations:**
  - It is a reanalysis grid, not on-site measurement.
  - Indoor or outdoor status is unknown; all events are assumed outdoor, which is typical for the CZ summer season.
  - Lane orientation is unknown, so wind can't be split into head- and tailwind.
  - The ground surface is known only for Blšany (grass).

---

## Step 4 – The coach's three questions (Phase 4A, 2026-10-13)

**Goal:** answer Q1 (lane colour), Q2 (passing onto intact/neutered male/female) and Q3 (everything per competition). Nothing in the processed tables is changed. Code: `src/flyball/lane.py`, `partner.py`, `competition.py`, new helpers in `stats.py`; `scripts/run_phase4a.py` rebuilds `reports/phase4a/*.csv` (16 tables) and 5 draft figures in `figures/phase4/` in about 55 s. Plain-language walk-through: `notebooks/04a_questions.ipynb`.

### 4.0 Conventions for yes/no questions
- **Two tests per result:**
  - a difference with a 95 % CI and a corrected p-value (Holm within a family; Benjamini-Hochberg for the 28 ring-day screen);
  - an **equivalence test (TOST)** against the smallest difference that matters: **0.05 s per dog run** (decided in planning), 0.2 s per heat, 0.02 s per start or pass, 2 percentage points (pp) for any rate.
- **Four verdicts** (`stats.verdict`): *meaningful difference*, *real but negligible* (significant but proven inside the margin), *no effect (equivalent)*, *inconclusive*.
- **New helpers in `stats.py`:**
  - `tost`, `verdict`, `bh`, `wald_joint`, `wald_equal`;
  - `speed_frame`: the valid-speed run table, now shared with `dog_run_model`;
  - `absorbed_ols`: OLS within groups by demeaning, errors clustered, with a degrees-of-freedom correction for the absorbed groups. It replaces a dog-dummy OLS that took 11 s per fit;
  - `crossed_mixed`: MixedLM with crossed random intercepts (`vc_formula` on a single group);
  - `mixed_table`, `mixed_fe_cov`;
  - `DOG_RUN_FORMULA`: shared by `dog_run_model` and the Q3 speed index.
- **`metrics.HELD_PASS_S = 1.0`:** a pass slower than 1 s was held back on purpose. It is used for robustness checks in Q1 and as its own outcome in Q2 (see 4.3).

### 4.1 How lanes are assigned (`lane.lane_assignment`)
- **Finding:** the lane is drawn **once per race**, not per heat:
  - only **4 lane switches in 6,211** consecutive heats of the same race-team (0.06 %);
  - the **first team listed on the sheet is always blue** (4,226 of 4,226 paired heats);
  - the 2,332 race-teams are split exactly 1,166 red / 1,166 blue;
  - no WRFT team got one lane more often than chance (red share 48–58 %, all Holm p = 1.0).
- **Consequences:**
  - lanes follow the running order, not team strength;
  - heats of one race share their lane, so every lane model **clusters standard errors on race** (1,172 races; 287 with WRFT).

### 4.2 Q1 – lane colour (`lane.py`)
- **Run time** (`lane_run_effect`), blue minus red. Two models, both comparing a dog with itself:
  - *mixed:* the Phase 3 dog model plus the lane;
  - *within dog-day:* `absorbed_ols` within dog × ring-day, clustered on race.

  | Sample | Runs / dogs | Mixed | Within dog-day (95 % CI) | Verdict |
  |---|---|---|---|---|
  | Field | 32,777 / 903 | +0.0065 s | +0.0064 s (0.003 to 0.010) | real but negligible |
  | WRFT | 4,340 / 50 | +0.0034 s | +0.0060 s (−0.006 to +0.018) | no effect (equivalent) |

  The within model drops 33 field runs whose dog ran only once that day (no comparison possible).
- **Per ring-day** (`lane_by_ring_day`, all dogs, one model with a lane term per ring-day):
  - the effect **differs between ring-days** (Wald χ² = 77.6, 27 df, p = 9 × 10⁻⁷);
  - 7 of 28 ring-days are significant after BH. In 6 the blue lane is slower (Máchale both days, Czech championship Sunday, EFC ring 2 Sunday, Budějckej ring 1 Sunday, Eager's Cup ring 1 Saturday) and in 1 the red lane is slower (Eager's Cup ring 2 Saturday);
  - **every ring-day is inside ±0.05 s**: the largest is +0.032 s per run (EFC ring 2, 30 Jul).
  - Interpretation: real local ring set-up asymmetries, all far too small to matter. The two Eager's Cup rings point in opposite directions on the same day, so it is not a general orientation effect.
- **Every other outcome** (`lane_outcomes`, 11 outcomes × 2 samples, Holm within each sample):
  - heat outcomes compare the same team on the same ring-day; dog outcomes the same dog;
  - **field:** all equivalent (clean time, start, pass, `ok` share, clean-heat and all fault rates), except the heat win rate, which is inconclusive (−1.1 pp, CI −4.0 to +1.9);
  - **WRFT:** run, clean heat and start times are equivalent; fault and win rates are inconclusive (287 races are too few for ±2 pp).
  - **WRFT pass time:** +0.044 s blue (CI 0.013–0.075, Holm p = 0.054). This comes from held-back passes. With passes > 1 s left out it is **+0.007 s** (CI −0.009 to +0.023), so the row "pass time, held passes left out" was added to the family. The field shows the same: +0.0105 s with held passes, +0.003 s without.
- **Answer:** lane colour has no effect that matters. No lane strategy is needed.

### 4.3 Q2 – passing onto intact/neutered male/female (`partner.py`)
- **Frame** (`pass_frame`):
  - 3,350 WRFT slots at positions 2–4, minus 89 without a pass value and 2 whose incoming dog is unknown (1 overlap), gives **3,260 pass attempts** (296 faults);
  - the incoming dog's age and its run in the same heat are joined by `row_id` and position − 1.
  - Incoming categories: neutered male 1,167 passes / 19 dogs; neutered female 1,365 / 17; intact male 515 / 8; **intact female 213 / 2 dogs**.
- **Finding 1 – age confound:** incoming intact dogs are much younger (median 1.9–2.3 years vs 4.8–5.7 years for neutered dogs). So every model is fitted twice:
  - **category:** `C(incoming) + C(own) + position + hurdle step + ring-day`;
  - **adjusted:** the same plus both dogs' ages and the team.
- **Finding 2 – held passes dominate the mean.**
  - The first fit gave "intact male incoming: +0.26 s pass time" (CI 0.07–0.45). With passes > 1 s left out it dropped to +0.02 s (CI −0.03 to +0.08).
  - **Decision:** split the pass into two outcomes:
    - **racing pass time** (≤ 1 s, 2,763 passes);
    - **held-pass rate** (> 1 s; 139 of 2,902 timed passes, 4.8 %).
  - **Deviation from the plan:** the plan had "pass time" as one outcome. The old version is kept as a sensitivity row.
- **Model:** `crossed_mixed` with random intercepts for **both the outgoing and the incoming dog**. The category effect is a between-dog trait, so its CI reflects the number of incoming dogs, not passes. Tested on synthetic data: the CI is more than 3 times wider than naive OLS. Outcomes:
  - racing pass time;
  - held-pass rate;
  - `ok` share;
  - early-pass rate;
  - the outgoing dog's log run time.

  Rates are linear-probability models. All contrasts are against an incoming neutered male.
- **Results** (`partner_contrasts`, `partner_joint`):
  - **No joint test is significant after Holm** over the 5 outcomes, in either specification: racing pass time p = 0.42, `ok` share 0.15, early-pass 0.62, run time 0.97 (category spec).
  - **Held passes onto intact males: +10.6 pp** (CI 3.1–18.1; adjusted +11.7 pp, CI 3.2–20.3). Its joint test is p = 0.042, Holm p = 0.21 over the 5 outcomes, so it is reported as a **lead, not a proven effect**.
  - Verdicts are mostly *inconclusive*: 2–8 dogs per intact group cannot prove equivalence within ±0.02 s. The outgoing dog's run time is equivalent for neutered female vs neutered male.
- **Interactions** (`partner_interactions`):
  - **sex × sex:** nothing (all Holm p ≥ 0.46);
  - **neutered × neutered on racing pass time:** +0.105 s, Holm p = 0.003. Fitted again as 4 pairing cells against neutered → neutered, the only outlier is **intact → intact** (64 passes, young dogs on both sides): +0.053 s (CI −0.04 to +0.15, p = 0.28). This is read as inexperience on a small cell, not a sex/neuter effect.
- **Sensitivity** (`partner_sensitivity`):
  - **Variants:** sex only; neutered only; intact females left out; the 480 passes involving a dog under 18 months left out; `ok` = 0 s and 0.08 s; held passes included; logistic GEE (exchangeable within the outgoing dog) for the two rates.
  - **No conclusion changes.** The held-pass signal is stable: +10.6 pp without the intact females, and +14.1 pp (CI 5.4–22.7) without the under-18-month dogs.
- **Answer:** no measurable effect of the incoming dog's sex or neuter status on racing performance. Passes onto young intact males are held back more often, which is a question for the handlers. The data are thin (2 intact females, 8 intact males), so this is "no evidence", not proof of absence.

### 4.4 Q3 – per competition (`competition.py`)
- **Unit:** a competition day (competition × date; the 2 rings of one event are combined per date). There are **20 WRFT competition days**. MED's Trophy and Budějckej ring 1 have no WRFT rows and appear only in the field index.
- **Dog-adjusted speed index** (`speed_index`):
  - built from the Phase 3 dog model's ring-day effects, centred on the season average with the full covariance;
  - it answers "how fast did the same dogs run here vs an average day";
  - field range **−2.0 % to +1.9 %** (about ±0.08 s per run);
  - slowest days: the two hottest (Máchale Sat 30 °C, EFC Sat 29 °C); fastest: Budějckej (October);
  - temperature is not the whole story: Budějckej Saturday was 19 °C, and the other 9 °C day (Eager's Cup Sunday) was not fast.
- **`competition_days`** (20 rows):
  - `metrics.team_summary` and `attribution_summary` per day;
  - gap to division peers (`within_division_gap`, clustered on team, Holm over the days) for clean time and win rate;
  - WRFT and field speed index, the lane effect (inverse-variance mean over rings), and the weather (ring means; maxima for gusts and rain).
  - **WRFT win rate below its peers on 4 days after Holm:** Eager's Cup Sun −19 pp, Flyvaryors Sat −21 pp, EFC Sun −39 pp, Czech championship Sun −23 pp. **Clean time never differed** from the peers after Holm. Faults, not speed, lose the bad days.
  - **Avoidable losses peak at Budějckej Sunday (69 %),** the day WRFT dogs were fastest (−2.8 %).
- **`competition_teams`:** each WRFT team × competition, with its rank in its main division (the one with most heats).
- **`dog_by_competition`** (247 rows): each dog's median run vs its own season median, plus passes and faults; descriptive, since hurdle and position vary.
  - The clearest cluster: the **season opener** (Hanácké; Sirius, Bailey, Dexter 0.2–0.3 s slow).
  - Gordon (15 cm height dog) swings the most.
- **`season_trend`:** `log_rt ~ months + position + hurdle + (1 | dog)`:
  - WRFT **−0.29 % per month** (CI −0.36 to −0.22, about −0.013 s per run per month); field −0.19 %;
  - the trend carries venue and weather; 4B fits it together with temperature.
  - **Deviation from the plan:** the planned spline sensitivity was replaced by the per-day speed index, which already shows the non-linear course of the season.
- **Joining weather:** `weather_day.csv` dates are strings, while race dates are datetimes. They are converted before the join, and a test checks that no WRFT day lacks weather.

### 4.5 Checks, tests and outputs
- **Tests:** 8 new in `tests/test_phase4a.py` (**92 in total**, all passing).
  - Synthetic: TOST and verdict values; BH and the Wald tests; `absorbed_ols` equals a dummy regression; `crossed_mixed` recovers a planted partner effect with an honest CI.
  - Real data: lanes drawn per race; every lane outcome has a verdict and a consistent CI; the Q2 frame holds only WRFT passes at positions 2–4 onto known dogs, and racing and held passes partition the timed passes; competition days add up to all decided WRFT heats, carry weather, and the speed index is centred.
- **Figures** (dataviz skill; colour roles from `plots/style.py`; the new aqua ↔ orange diverging scale was validated with CVD ΔE 9.2, and its below-3:1 aqua is backed by a colour bar and the CSV table):
  - `lane_ring_days`: forest plot with the ±0.05 s band;
  - `lane_wrft_dogs`: red/blue slope chart;
  - `partner_forest`: small multiples, both specifications;
  - `competition_days`: 5 stacked panels per competition day;
  - `dog_by_competition`: heatmap.
- **Outputs:** `reports/phase4a/`: `lane_*` (6), `partner_*` (5), `competition_days`, `competition_teams`, `dog_by_competition`, `speed_index`, `season_trend`.

## Step 5 – Weather analysis and ideal line-up (Phase 4B, 2026-10-13)

**Goal:** support or refute the coach's weather hypothesis (temperature, wind, humidity, rain), and recommend the ideal line-up. Nothing in the processed tables is changed.
- **Code:** `src/flyball/weather_effects.py`, `src/flyball/lineup.py`; new helpers in `stats.py`.
- **Rebuild:** `scripts/run_phase4b.py` rebuilds `reports/phase4b/*.csv` (29 tables) and 6 draft figures in `figures/phase4/` in about 55 s.
- **Walk-through:** `notebooks/04b_weather_lineup.ipynb`.
- **New dependency:** scikit-learn 1.9.1, for the gradient-boosting check (user decision).

### 5.0 Shared helpers
- **`stats.absorbed_ols(..., small_sample=True)`:** t(G − 1) CIs and p-values for few clusters. The default is unchanged; the 4A outputs were rebuilt and are byte-identical.
- **New functions:**
  - `stats.linear_combination`: estimate and CI of a sum of coefficients (e.g. the slope above a hinge);
  - `stats.tost(..., df=)`: t version of TOST;
  - `stats.eb_shrink_mean`: empirical-Bayes group means (one-way random effects).
- **Moved:** `lane._ok_imputed` → `metrics.ok_imputed`, now shared by 4A and 4B.

### 5.1 Analysis frame (`weather_effects.run_frame`, `heat_frame`)
- **Size:** 33,693 slots of known dogs (32,777 valid runs) and 8,464 decided heats, all matched to heat weather (`weather.attach`).
- **One model term per coach factor**, scaled to a realistic change:
  - temperature per 10 °C, with a hinge at 20 °C (separate slopes below and above);
  - humidity per 20 pp;
  - mean wind per 3 m/s;
  - **wet** = rain ≥ 0.1 mm in the last 3 h. Rain is used as dry/wet only, because millimetres are unreliable (log 3.4).
- **Collinearity** (`weather_correlations`):
  - temperature and humidity: r = −0.66, VIF ≈ 3;
  - gusts and mean wind: r = 0.93, so gusts are left to a sensitivity check;
  - season (months) and heat weather: r = 0.06.
- **New controls:**
  - `run_no_today`, the dog's n-th run that day (fatigue);
  - `heat_no_today` for teams;
  - `day2`, the second day of the event. The EFC's 4 single-day sheets are grouped by event, so 29 Jul = day 1 and 30 Jul = day 2.

### 5.2 Main model: within competition (`within_competition`)
- **Design:** `absorbed_ols` with **dog × competition** absorbed (team × competition for heat outcomes). Each dog is compared only with itself at the same event: Saturday vs Sunday, morning vs afternoon.
- **Controls:** position, hurdle step, `run_no_today`, `day2`.
- **Errors:** clustered on the **venue-day**, because both rings of an event share one weather. That gives 22 clusters (WRFT 20), with t(21) CIs.
- **Outcomes, field and WRFT:**
  - run time (32,765 field runs; 12 runs with no second run of the dog at the event dropped);
  - start time and racing pass time (≤ 1 s);
  - false-start, early-pass and run-fault rates;
  - clean heat time (4,763 clean heats);
  - clean-heat rate.
- **Verdicts:** Holm over the 5 weather contrasts within each outcome; TOST at the 4A margins (0.05 s per run, 0.2 s per heat, 0.02 s per start/pass, 2 pp).
- **Results (field):**

  | Contrast | Run time per run (95 % CI) | Verdict | Clean heat time (95 % CI) | Verdict |
  |---|---|---|---|---|
  | +10 °C below 20 °C | +0.003 s (−0.007 to +0.013) | equivalent | −0.06 s (−0.15 to +0.02) | equivalent |
  | **+10 °C above 20 °C** | **+0.083 s (+0.050 to +0.117), +1.9 %** | **meaningful** | **+0.71 s (+0.31 to +1.10)** | **meaningful** |
  | humidity +20 pp | +0.018 s (+0.007 to +0.030) | real but negligible | +0.04 s | equivalent |
  | wind +3 m/s | −0.007 s (−0.019 to +0.005) | equivalent | +0.01 s | equivalent |
  | rain in last 3 h | −0.005 s (−0.014 to +0.003) | equivalent | −0.01 s | equivalent |

- **WRFT dogs:** same direction (+0.072 s per run above 20 °C, CI −0.006 to +0.152), but inconclusive on their own. Wind and rain are equivalent to zero.
- **Faults:**
  - no weather contrast is a meaningful difference in the field sample; most are inconclusive (CIs wider than ±2 pp);
  - one WRFT-only hit: early passes −7.5 pp per +20 pp humidity (Holm p < 0.001). It is 1 of 40 WRFT tests, humid hours are the cool mornings, and the field shows nothing similar, so it is reported as a lead only.
- **Coach verdict** (`weather_verdict`, read on the field sample):

  | Factor | Speed | Faults |
  |---|---|---|
  | temperature | **supported above 20 °C** | inconclusive |
  | humidity | refuted (too small) | inconclusive |
  | wind | refuted | inconclusive |
  | rain | refuted | inconclusive |

### 5.3 Deviation from the plan: the second-day control
- **What happened:** the first fit, without `day2`, showed "warmer below 20 °C = more faults" (false starts +6 pp, early passes +5 pp, clean-heat rate −13 pp per 10 °C).
- **Why it was spurious:** Sunday was cooler than Saturday at 9 of the 11 two-day events (clearly so at 6: Heroltice, Žamberk, Crazy Cup, Máchale, Vodňany, EFC).
- **Fix:** with `day2` added, the fault signals vanished (false starts +0.4 pp, early passes −2 pp, both inconclusive). The run-time heat effect did not move (0.083 s). So `day2` became a standard control. The variant without it is kept in `weather_sensitivity`.
- **Side finding** (`weather_controls`): same team, same event, second day:
  - **clean-heat rate +18.9 pp** (field, CI 15.9–21.9; WRFT +16.0 pp, CI 9.5–22.5);
  - false starts −5.6 pp (WRFT −10.0 pp);
  - early passes −6.6 pp (WRFT −3.3 pp);
  - run time unchanged.

  The cause is unknown (nerves, a new ground, Sunday's race format). It is flagged for Phase 5 as a finding in its own right.
- **Fatigue:** each earlier run that day adds +0.005 s to the next run (field, CI 0.004–0.007; WRFT the same).

### 5.4 Robustness
- **Sensitivity** (`weather_sensitivity`, field, 5 outcomes × 20 variants plus the baseline; first written as 22, corrected in Step 7.4):
  - variants: no fatigue control; no second-day control; plus hour of day; hinge at 15 / 25 °C; apparent temperature; wet ground (≥ 1 mm in 24 h); gusts instead of wind; and each of the 11 competitions left out;
  - **run time above 20 °C: 0.062–0.097 s per run** in every variant that keeps the 20 °C hinge. With the hinge at 15 °C it is 0.040 s (the same rise spread over a wider range); with apparent temperature, 0.054 s;
  - **clean heat time above 20 °C leans on Máchale:** 0.71 s with it, 0.27 s without. The per-run estimate is the robust one.
- **Within day** (`weather_within_day`, dog × ring-day absorbed): only the diurnal swing of a few °C is left. Every temperature estimate is inconclusive; wind and rain stay equivalent.
- **WRFT mixed model** (`weather_mixed_wrft`, random dog + ring-day, competition fixed effects): the ring-day effect absorbs most day-level weather, so this is close to a within-day comparison. It gives −0.08 s below and +0.01 s above 20 °C, and is reported as a check, not as evidence.

### 5.5 Between days: weather vs venue (`day_meta`)
- **Design:** the field speed index per ring-day (4A) regressed on the day-mean weather and months, WLS with weights 1/SE², clustered on venue-day (28 ring-days, 22 venue-days).
- **R²:**
  - season only: 0.20;
  - weather only: 0.61;
  - **weather + season: 0.77**, and 0.57 when each event is predicted from the other events only (leave one event out).
- **Coefficients:**
  - +0.78 % per 10 °C (CI 0.29–1.26);
  - season −0.18 % per month;
  - wet day −0.84 %. Rainy days are cloudy and cool, and the within-competition model shows no rain effect, so this is read as sun/radiation, not rain.

### 5.6 Shape of the heat effect and the gradient-boosting check
- **Binned dog-adjusted run time** (`weather_curve`):
  - flat up to about 22 °C;
  - +0.36 % at 23 °C, +0.76 % at 25 °C, +1.8 % at 33 °C.
  - This is descriptive, across venues.
- **Gradient boosting** (`gbm_check`):
  - `HistGradientBoostingRegressor` on the dog-adjusted log run time (dog level, position and hurdle removed);
  - features: the 4 weather variables plus `run_no_today`;
  - **leave-one-competition-out CV** (11 folds), so an event is never trained and tested on.
- **Results:**
  - per run, R² = 0.01: single runs are mostly noise;
  - per ring-day, the weather model tracks slow days (correlation 0.38) while the fatigue-only model doesn't (−0.44). R² is below 0 for both, because the venue level of an unseen event is unknown;
  - permutation importance: fatigue 0.36, temperature 0.034, humidity 0.030, rain 0.007, wind 0.0005;
  - partial dependence on temperature steps up between 21 and 24 °C, which matches the hinge.
- **Deviation from the plan:** months and hour of day were first included as features but dropped. Leaving them out improved the day-level R² from −0.38 to −0.06; they extrapolate badly to an unseen event.

### 5.7 Line-up: dog profiles (`lineup.dog_profiles`)
- **Pool:** 42 WRFT dogs with ≥ 20 valid runs, whenever they last raced (user decision). Only dogs with ≥ 10 starts may run first (23 pool dogs).
- **Speed:**
  - MixedLM `log_rt ~ C(position) + hurdle_step + C(comp_day_id) + (1 + hurdle_step | dog)`, predicted on an average day;
  - the random slope lets a dog seen at one height borrow the team slope;
  - **9 dogs had a negative total slope** (faster over higher hurdles, not plausible) and were floored at 0.
- **Starts and passes:**
  - shrunken means of fault-free attempts ≤ 1 s, with `ok` = 0.04 s (`stats.eb_shrink_mean`);
  - false-start, early-pass and run-fault probabilities from `stats.eb_shrink_rate`;
  - a dog with no attempts gets the team value.
- **Height:**
  - the **typical** hurdle the dog set as the smallest dog, when it did so ≥ 3 times (`wrft_hurdle_check`); otherwise the master jump height;
  - **deviation from the plan**, which said "lowest": the mode is robust to single entry errors (e.g. Nina set 25 cm in 38 of 95 rows but 27.5 cm in the rest).
- **Spot-check:** Cookies, Maggie and Enola match their scorecard rows (starts, EB false-start rate). Speed agrees with the Phase 3 `adj_run_s` within about 0.05 s (the new model adds the hurdle slope).
- **Implementation note:** profile tables keep only scalars in `DataFrame.attrs`. A statsmodels fit stored there made pandas deep-copy it on every operation (backtest 30 s → 0.7 s), and arrays there broke `concat`.

### 5.8 Line-up: score and search (`score_orders`, `search`)
- **Expected heat time** = start(dog 1) + Σ run(dog, h_min, position) + Σ pass(dogs 2–4) + fault cost × expected number of faults.
  - h_min is the smallest dog's height.
  - Fault cost = **7.96 s**: the median rerun time of corrected faults, weighted (`metrics.fault_cost_seconds`).
- **Also reported:**
  - P(clean heat);
  - `no_fault_s` (start + runs + passes; not the FCI clean time, which is `runs_s`).
- **Search:** exhaustive, **111,930 sets × 24 orders = 2,686,320 line-ups**, vectorised (0.5 s).
- **A-team: Maggie > Enola > Pax > Alfie**:
  - 25 cm hurdle;
  - runs 15.95 s, 16.60 s without faults, **19.28 s expected**, P(clean) 0.70;
  - **plausibility check:** real WRFT heats with the Enola, Maggie and Alfie core ran clean times of 15.7–16.3 s at 27.5 cm.
- **Starter caveat:** Maggie leads off on only 14 starts. Enola first (156 starts) is 0.06 s faster when clean but 0.5 s slower in expected time. Advice: trial Maggie as the starter; until then Enola first is the safe choice.
- **Reserves:** Tyna (+0.07 s replacing Pax) and Alex (+0.13 s). Top-50 frequency: Enola 40, Maggie 37, Alfie 29, Pax 26, Tyna 19.
- **Speed only** (fault cost 0): Moon enters the best line-up. Her early-pass rate (13 %) costs more than her speed once faults count.

### 5.9 Line-up: current teams and the height dog
- **Current line-ups** (`current_line_ups`): each team's most-used 4-dog set and order at its last competition. XXL's last competition was Máchale (July).
- **Reordering gains** (`team_recommendations`), in expected seconds per heat:
  - **Hopefuls 2.25** (start with Maggie instead of Cookies: Cookies false-starts 34 %);
  - Zephyr 1.35;
  - XXL 1.03;
  - Maximini 0.36;
  - Wonders 0.11;
  - Dreamers and Nightfall 0.
- **Deviation from the plan:** swaps only use **bench dogs** (pool dogs in no current line-up). The first version moved Enola and Maggie into every team, which is not actionable. Pax is the best bench dog for all 7 teams, then Sunny and Ashley; the top 3 are listed per team. Pax last raced in July, so his availability needs checking.
- **Height dog** (`height_dog`): best line-up with each small pool dog vs the best without a dog under 25 cm.

  | Dog | Height | Partners' hurdle saving | Net vs without |
  |---|---|---|---|
  | Easy | 20 cm | +0.41 s | −0.55 s |
  | Kesha | 22.5 cm | +0.27 s | −1.10 s |
  | Dusty | 22.5 cm | +0.27 s | −2.41 s |
  | Gordon | 15 cm | +0.67 s | −2.43 s |

  None pays off in a top team: a small dog would need to run within about 0.1–0.2 s of the big dogs.

### 5.10 Line-up: back-test and stability
- **Back-test** (`backtest`): profiles fitted on Apr–Jul, tested on the 261 decided Sep–Oct WRFT heats with four named WRFT dogs.
  - **Excluded:** 47 heats with a dog that has no Apr–Jul history (Easy, Kent, Milo). That leaves 214 heats, 137 of them clean.
  - **Clean time:**
    - model MAE 0.34 s, Spearman 0.91;
    - naive baseline (sum of each dog's raw training median) MAE 0.31 s, Spearman 0.89.
  - **By height:** at 15 cm the model's bias is −0.32 s against +0.54 s for the baseline (MAE 0.50 vs 0.64 s). At 27.5 cm the baseline is better (MAE 0.31 vs 0.36 s).
  - **Reading:** the naive sum already knows each dog's usual height. The model adds value where the height is unusual, which is exactly what the search needs.
  - **An intercept-only speed model was also tried:** MAE 0.33 s, but bias +0.49 s at 15 cm. The random slope was kept.
  - **P(clean):**
    - Brier 0.234 vs 0.243 for the constant training rate; AUC 0.55;
    - predicted 0.56 vs observed 0.64: the team got cleaner over the season;
    - so the fault part of the ranking is a tilt, not a forecast.
- **Stability** (`stability`, 50 resamples of WRFT competition days, profiles refitted and search redone):
  - share of resamples each dog is in the best line-up: Enola 100 %, Alfie 72 %, Pax 58 %, Maggie 56 %, Alex 34 %, Tyna 32 %;
  - the exact A-team stays in the top 5 in 38 % of resamples;
  - **robust advice:** the core (Enola, Alfie, Maggie) plus two of Pax, Alex and Tyna, in the right order.

### 5.11 Checks, tests and outputs
- **Tests:** 8 new in `tests/test_phase4b.py`, **100 in total**, all passing.
  - **Synthetic:**
    - `small_sample` CIs are wider than the normal ones, and `linear_combination` adds the coefficients;
    - `eb_shrink_mean` pulls small groups harder;
    - a planted heat effect is recovered by the within-competition model. The check is on point estimates; CI coverage was checked over 20 seeds and the estimates are unbiased;
    - the search finds the known best set and starter in a 6-dog toy pool;
    - the smallest dog sets the hurdle, and the order only moves the start, pass and position terms.
  - **Real data:**
    - every valid run and decided heat has weather;
    - `day2` is constant per ring-day and correct for the EFC;
    - effects and verdicts are complete, with venue-day clusters;
    - the pool has 42 profiled dogs with probabilities in [0, 1] and slopes ≥ 0;
    - the backtest tests only Sep–Oct, and Easy is unprofiled.
- **Figures** (dataviz skill; colour roles from `plots/style.py`, already validated):
  - `weather_forest`: field in ink, WRFT in violet, with the margin bands;
  - `heat_curve`: binned means plus the GBM partial dependence;
  - `weather_vs_venue`;
  - `lineup_breakdown`: stacked start / runs / passes / fault cost per line-up. It replaces the planned "line-up cards", which are left for the Phase 6 deck;
  - `height_dog_tradeoff`;
  - `lineup_backtest`.
- **Outputs:** `reports/phase4b/`:
  - `weather_*` (14): correlations, effects, controls, verdict, within_day, mixed_wrft, sensitivity, day_fit, day_coefficients, days, curve, gbm_scores, gbm_importance, gbm_pdp;
  - `dog_profiles`;
  - `lineup_*` (14): top, speed_only, dog_frequency, reserves, teams, comparison, height_dog, backtest, backtest_heats, backtest_by_hurdle, backtest_calibration, stability, stability_dogs, meta.

---

## Step 6 – Synthesis (Phase 5, 2026-10-13)

**Goal:** rank every finding by business impact in one currency, turn each into an action for the coach, and fix the storyline for the deck. Nothing in the processed tables or in the Phase 3–4 outputs is changed.
- **Code:** `src/flyball/synthesis.py`; a new public helper `lineup.score_line_ups` (`lineup.comparison` now uses it, and its output is byte-identical).
- **Rebuild:** `scripts/run_phase5_synthesis.py` rebuilds `reports/phase5/` in about 25 s. It reads `data/processed/` and the Phase 3–4 tables.
- **Walk-through:** `notebooks/05_synthesis.ipynb`.
- **Written deliverables:** `reports/findings.md` (findings ranked by impact, with evidence, confidence and actions) and `reports/storyline.md` (slide-by-slide outline).
- **User decisions (planning):** rank with a computed impact ledger rather than by judgement; the storyline is a Markdown outline that Phase 6 turns into the slide-text file.

### 6.1 Impact ledger (`synthesis.impact_ledger`)
- **Currency:** expected **extra heats won per season** by WRFT. A won heat is the good result (2.3).
- **Engine:**
  - the Phase 3 WRFT heat-win model (logistic: speed gap, start gap, own and opponent faults; clustered on race), refitted with `stats.heat_win_models`;
  - a lever changes the model inputs of the heats it applies to, and the ledger sums the change in predicted P(win).
- **Sample:**
  - WRFT's decided heats **against other clubs only**: 907 heats (WRFT won 39.0 %), of which 897 have a typical speed on both sides and enter the model;
  - results are scaled by 907/897;
  - **why:** WRFT-vs-WRFT heats (207 team rows) are left out, because a club-wide fix can't win the club a heat against itself.
- **Two kinds of change** (`Change`):
  - **Fault change ("thinning"):** the share of heats with a fault moves to a target, by removing faults at random among the faulted heats (or adding them at random to clean heats). Each heat then has a probability of carrying each of its 3 own fault types, and P(win) is averaged over the 8 combinations, exactly rather than by simulation.
  - **Shift:** the team's typical clean time (`speed_gap`) moves by a constant or by a per-heat amount.
- **Uncertainty:** 2,000 draws of the model coefficients from the cluster-robust covariance (seed 2023). Where the size of the lever is itself an estimate (a peer gap, the day-2 effect, the heat slope), it is drawn from its normal approximation too. A draw that reverses a gap counts as "no change".
- **Levers** (39 rows in `impact_ledger.csv`, each with a stable `lever_id`):
  - **Fault gaps to the division peers:**
    - each WRFT team × fault type where the team is worse than its peers (Phase 3 `peer_benchmark`; 22 rows);
    - each fault type for all teams together (3 rows);
    - every gap at once (1 row).
  - **Line-ups:** each team's recommended order (same dogs) and best bench swap (Phase 4B `team_recommendations`), plus all reorders together. See 6.3.
  - **Second-day effect:** day 1 of a two-day event as clean as day 2. See 6.2.
  - **Heat:** WRFT keeps its full speed above 20 °C while its opponents slow down. The per-heat penalty is 4 × 0.083 s × (°C − 20)/10, from Phase 4B `weather_effects` (field, run time).
    - **Why it is an upper bound:** heat slows every team (5.2), so it can only change results if WRFT copes better than its opponents.
  - **Ceiling:** no own faults at all. It is a reference for scale, not a target.
- **Results** (extra wins per season, 95 % CI; win-rate points out of 907):

  | Lever | Extra wins | Win rate |
  |---|---|---|
  | No own faults at all (ceiling) | +148 (127–165) | +16.4 pp |
  | Saturday as clean as Sunday | +28 (17–42) | +3.1 pp |
  | All teams run their recommended order | +27 (20–33) | +3.0 pp |
  | Every fault gap to peers closed | +26 (21–33) | +2.9 pp |
  | – false starts / early passes / run faults | +11.5 / +7.9 / +6.2 | |
  | Hopefuls reorder (Maggie starts, not Cookies) | +12.1 (8.9–14.5) | |
  | Zephyr / XXL / Maximini reorder | +8.5 / +4.0 / +2.5 | |
  | Zephyr's run-fault gap; XXL's false-start gap | +4.4; +3.6 | |
  | Bench swaps (Pax), per team, not additive | +3.4 to +45 | |
  | Hot days, upper bound | +3.5 (1.8–5.4) | +0.4 pp |
  | Dreamers and Nightfall reorder | 0 (already optimal) | |

- **Levers in different groups overlap.** For example, the Hopefuls reorder is itself a false-start fix. Rows within a group add up (the teams' heats don't overlap); rows across groups don't.
- **Hand checks:**
  - XXL false starts down to peers: done by hand with `fit.predict` on the faulted heats, 3.631 vs 3.631 in the ledger;
  - day-2 lever: Monte Carlo over 400 simulated seasons, 28.18 vs 28.22.
- **Caveat:** these are model-based what-ifs from observational data (association, not proven cause). They rank the levers; they are not exact promises.

### 6.2 Second-day effect at heat level (`synthesis.day2_fit`)
- **What:** the Phase 4B team model (weather terms, hurdle, heat number of the day, `day2`; team × event absorbed; clustered on venue-day, t(21)), with the 3 heat-level fault flags as outcomes, on WRFT heats.
- **Why:** 4B measured the day-2 effect per start, per pass and per run (dog level). The ledger needs it per heat.
- **Result** (`impact_day2_faults.csv`), day 2 − day 1:
  - false-start heats **−11.6 pp** (CI −14.5 to −8.7);
  - early-pass heats **−8.2 pp** (−14.6 to −1.8);
  - run-fault heats −0.1 pp (no change).
  - This agrees with 4B's dog-level −10.0 pp per start.
- **Lever:** applied to the 468 day-1 heats of two-day events (scaled count). Draws are capped at 0, so the lever never adds faults.

### 6.3 Deviation during the phase: how line-up levers are scored
- **First version:** added the difference between the recommended and the current line-up (Phase 4B profiles) to *all* of the team's 2023 heats.
- **Problem:** Zephyr's bench swap came out at +42 wins.
  - Zephyr's current line-up (with the 15 cm height dog Gordon, typical runs ~21.8 s) ran only at its last competition.
  - Most of Zephyr's season was run by faster line-ups (season median clean time 18.6 s).
  - So a −2.6 s shift was being added to heats that never had the slow line-up.
- **Check:** each current 4-dog set ran only 7–15 heats in the whole season, too few to anchor on.
- **Fix:**
  - **two model-based arms against the same opponents:**
    - the reference arm sets the team's typical clean time to the current line-up's predicted runs and its fault probabilities to the line-up's;
    - the lever arm does the same for the recommended line-up;
  - **opponents:** the ones the team met at its **last competition** (where the current line-up raced; 12–28 heats per team);
  - **scaling:** the change is scaled to the team's season volume.
- **Check of the arms:** the model's runs for the current line-ups are close to the teams' observed typical clean time at that competition (Dreamers 16.2 vs 15.8 s, Hopefuls 16.2 vs 16.2, Maximini 17.0 vs 17.0; Zephyr 21.8 vs 23.4 and XXL 19.0 vs 21.6, where the model is optimistic).
- **A second change: start and pass time count as speed.** The recommended line-up's speed change is the change in *start + runs + passes* (`no_fault_s`), applied through `speed_gap`, because a second saved anywhere in the heat counts the same. The heat-win model's own `start_gap` term (odds ratio 0.15 per s, CI 0.009–2.5) is too imprecise to carry a lever.
  - **Effect:** in the first version, which counted runs only, Maximini's reorder (it mainly saves pass time) came out at −0.4 wins; now it is +2.5.
- **Results** (extra wins): Zephyr's bench swap +45; Hopefuls reorder +12.1. The bench swaps stay optimistic: a much faster team would be seeded into a faster division and meet faster opponents. Profile values are taken as known, so the line-up CIs cover the win model only.

### 6.4 Key numbers (`synthesis.key_numbers`, `KEYS`)
- **What:** `reports/phase5/key_numbers.json` holds **97 numbers**. Each has a value, unit, CI (where the source has one), source table and log step, e.g. `wrft_false_start_heats` = 0.1577 from `phase3/team_summary.csv`, log 2.5.
- **Coverage:** every number quoted in `reports/findings.md` and on the slides (`reports/storyline.md` names the keys per slide).
- **Rule:** each key selects exactly one table row, by exact column values, or an explicit aggregate (count, min, max, |max|). An ambiguous or missing row raises an error.
- **Why:** Phase 6 will read slide numbers from this file, so the deck can't drift from the analysis.
- **New numbers found while writing:**
  - WRFT's win rate against other clubs: **39.0 %** over 907 heats (38.7 % in the 897 model heats). The findings quote 39.0 %.
  - "Heats with a result" = 1,116 (`team_summary`, ties included) vs 1,114 decided wins and losses (2.4). The findings say which count they use.
  - Field per-attempt fault rates used as action-plan targets: false starts 10.6 % per start, early passes 8.8 % per pass (`team_summary.pass_fault_rate`).

### 6.5 Consistency audit
- **Reproducibility:** all six phase scripts were rerun. Every committed output (tables and figures, Phases 2–4B) came back **byte-identical**, including after the `lineup.comparison` refactor. Running the Phase 5 script twice gives identical files (fixed seeds).
- **Cross-check:** the headline numbers in the log, `plan.md` and the CSVs agree; no corrections were needed:
  - avoidable losses 155 / 23.5 %;
  - the A-team at 19.28 s expected;
  - the day-2 effect +16.0 pp (WRFT) and +18.9 pp (field);
  - the heat effect +0.083 s per run;
  - the lane maximum 0.032 s;
  - Hopefuls reorder 2.25 s.

### 6.6 Checks, tests and outputs
- **Tests:** 6 new in `tests/test_phase5.py`, **106 in total**, all passing.
  - **Synthetic:**
    - `thin` hits the target rate in both directions and never adds faults when going down;
    - `expected_wins` with observed inputs equals the model's own prediction;
    - signs and sizes (fewer faults > 0, more faults < 0, faster > 0, partial < ceiling);
    - a reference arm equal to the lever gives exactly 0.
  - **Real data:**
    - the ledger frame holds only WRFT heats against other clubs, with no missing inputs;
    - every ledger CI contains its estimate, lever ids are unique, the ceiling is the maximum, and no gap lever costs wins;
    - `key_numbers.json` is up to date and matches the ledger.
- **Outputs** (`reports/phase5/`):
  - `impact_ledger.csv` (39 levers);
  - `impact_day2_faults.csv`;
  - `impact_meta.csv` (sample sizes, win rates, draws, seed);
  - `key_numbers.json` (97 numbers).
- **Written:** `reports/findings.md` (9 findings ranked by impact, action plan, open questions, limitations) and `reports/storyline.md` (13 main slides with timings that add up to about 12 min, an appendix, and the charts Phase 6 must build).

---

## Step 7 – Phase 6: visualisation and presentation (Hungarian) (2026-10-13)

No data was changed in this phase. Everything below re-presents the Phase 3–5 outputs.

### 7.1 Decisions and tooling
- **User decisions:** the deck and the website are **Hungarian only**. The deck is a talk part (15 slides, 12:00 by the slide timings) plus a detailed appendix (20 slides) in **one PDF**. The website is **interactive** and sits with the PDFs in **one self-contained folder**, `prezentacio/`, for upload.
- **PDF engine:** headless Chromium through Playwright (`playwright` added to `pyproject.toml`). Chromium needed three system libraries that were missing (`libnspr4`, `libnss3`, `libasound2t64`). There is no root access, so they were fetched with `apt-get download` and unpacked into `~/.local/share/chromium-deps/` (outside the project). `report/deck.py` adds that folder to `LD_LIBRARY_PATH` when it exists. On another machine, `uv run playwright install --with-deps chromium` does the same job.
- **Font:** Source Sans 3 (SIL Open Font License), static TTFs in `src/flyball/report/static/fonts/`. It is used by the charts, the deck and the site.
- **Website libraries:** Vega 5.30.0, Vega-Lite 5.21.0 and vega-embed 6.26.0, pinned and bundled in `src/flyball/report/static/vendor/`, so the site works offline and on any static host.

### 7.2 Numbers: no number is typed into the text
- **Text file:** all slide and site text is in `src/flyball/report/text_hu.toml`. An English deck would need only a `text_en.toml`, plus a pass over the chart labels in `plots/deck.py`.
- **Placeholders:** every number in the text is a placeholder, `{key|modifiers}`, resolved by `report/numbers.py` from three sources:
  - `key_numbers.json` (the 97 Phase 5 numbers);
  - `numbers.derived()`: 40 counts and definitions read from the processed tables, the report CSVs and code constants (e.g. 8,543 team rows, 42 pool dogs, the 0.12–0.35 s pass window, the 20 °C hinge), each with its source;
  - `{dog.<name>.<column>}`, which reads the dog scorecards.
- **Hungarian formatting:** decimal comma, `40,8%`, `4,28 mp`, a true minus sign, `%-pont`, and the CI written as `(KI 20–33)`.
- **Test:** every placeholder must resolve, and no digit may appear outside a placeholder, except years, Q1–Q3, "95%" and file paths.

### 7.3 Charts (`plots/deck.py`, 27 SVGs in `figures/phase6/`)
- **New charts:**
  - the season calendar (each competition-day tile coloured by its clean-heat rate against the field, with the temperature and the 4 days below the peers marked);
  - the heat-strip timeline (Hopefuls vs FOFR DOG at Hanácké: 16.27 s, lost on Moon's uncorrected early pass, against 18.43 s);
  - the impact-ledger bars and the five-lever "you are here" strip;
  - the Saturday → Sunday slope chart (pooled clean-heat rate, WRFT 47 % → 62 %, field 50 % → 65 %; raw shares, so a little different from the model's +16.0 pp);
  - the stability bars;
  - the per-competition panels;
  - team gaps to the peers as small multiples;
  - the heat-win model as a forest plot.
- **Redrawn in Hungarian:** the Phase 3–4 drafts, using the same colour roles as before.
  - In the dog quadrant, **orange = training targets** (findings F3–F4) and **violet = the A-team**.
- The SVG text is drawn as outlines, so the charts look the same everywhere. The output is deterministic (fixed hash salt, no date metadata).

### 7.4 Corrections found while building
- **Sensitivity variants:** `weather_sensitivity.csv` holds **21 specifications: the baseline plus 20 variants**, not 22 as written in 5.4, `findings.md`, `storyline.md` and `plan.md`. All four now say 20. The conclusion is unchanged.
- **Hottest day:** the hottest racing hour was 33.5 °C. The slides round it to 34 °C, where `storyline.md` said 33 °C.
- **Below-peer days:** 3 of the 4 days where WRFT fell below its peers were Sundays. This does not contradict the Saturday finding. The day-2 effect compares the same teams with themselves, and on Sundays the peers are cleaner too (field +18.9 pp). The deck states both facts as they are.

### 7.5 The deck (`report/deck.py`, `templates/deck.html.j2`, `deck.css`)
- **Format:** 35 slides at 1280 × 720.
  - Talk (15): cover, summary, season, what wins, a real heat, ledger, running order, Saturdays, fault habits, line-up, Q1 + Q2, weather, Q3, action plan, methods.
  - Appendix (20): data and cleaning, heat-win model, ledger method and table, team gaps, team table, dog tables (2), start and pass window, Q1 details, Q2 details, competition days (2), dog × competition heatmap, weather robustness, day 2, line-up breakdown, back-test and reserves, open questions, glossary.
- **Tables:** built from the CSVs by small providers (`deck.PROVIDERS`), e.g. the line-up cards from `lineup_teams.csv` and the 42 pool dogs sorted by adjusted run.
- **Speaker notes:** a separate A4 PDF built from the same text, with the timing for each slide.
- **Visual check:** every slide was rendered to PNG and inspected. Fixed during the check: overflowing tables (the ledger table now shows levers of ≥ 5 wins; the full ledger is on the site and in the CSV), a doubled unit, over-precise percentages, and the Q1/Q2 layout.

### 7.6 The website (`report/site.py`, `templates/site.html.j2`, `templates/site/*`)
- **Sections:** summary (with a PDF download and the speaker notes); clickable season calendar; what wins; interactive impact ledger (Vega-Lite, with tooltips) and the full 39-lever table; levers (line-up cards, Saturday slope, interactive dog quadrant); **line-up builder**; Q1/Q2; **competition-day explorer** (team results, faults and weather for each day); weather; **sortable and filterable dog table** (all 50 dogs); action plan; methods with the appendix charts; glossary; downloads.
- **Data:** goes in `assets/data.js` as a script, not as JSON, so the page also works when opened straight from disk.
- **Line-up builder:** `assets/lineup.js` ports `lineup.score_orders` line by line.
  - `site.lineup_model()` recomputes the Phase 4B profiles, because the profile CSV does not store the model's position terms, and exports exactly the arrays the search used.
  - **Parity:** on all 15 line-ups of `lineup_comparison.csv`, the exported arrays and the JavaScript (run under Node in the tests) agree with Python within 0.0002 s. The A-team scores 19.28 s; Hopefuls goes from 21.99 s now to 19.74 s with the recommended order.
  - "Best order" keeps the Python rule: only a dog with ≥ 10 starts may open.
- **Fixes during the browser check:** two Vega quirks. In Vega 5.30, `cornerRadiusEnd` put the bars in the wrong place, and the y-axis label column was too narrow (fixed with `minExtent`). Also fixed: horizontal overflow at phone width (grid `min-width`).
- **Browser check:** headless Chromium shows no console errors at 1280 px or 390 px and no horizontal scroll. The calendar, day explorer, builder and dog table were all clicked through.
- **CSV downloads (`adatok/`):** dog scorecards, competition days with weather, teams per competition day, and the full impact ledger. They are UTF-8 with a BOM, so Excel opens them correctly.

### 7.7 Checks, tests and outputs
- **Tests:** 7 new in `tests/test_phase6.py`, **113 in total**, all passing. They cover:
  - the formatter;
  - placeholder resolution and the no-typed-numbers rule;
  - that every figure exists;
  - Python parity of the exported line-up model;
  - JavaScript parity under Node;
  - that every link in `index.html` points to a file inside the folder.
- **Reproducibility:** running `scripts/run_phase6_presentation.py` twice gives byte-identical files (PDF dates are blanked). It takes about 7 s.
- **Outputs:**
  - `prezentacio/`: `index.html`, `WRFT_2023_elemzes.pdf`, `WRFT_2023_eloadoi_jegyzet.pdf`, `OLVASS_EL.md` (how to upload), `assets/`, `adatok/`;
  - `figures/phase6/`;
  - `notebooks/06_presentation.ipynb`.
  - The deck HTML in `reports/phase6/` is a build intermediate with local `file://` paths, so it is git-ignored.

### 7.8 Language revision (user request: "make it read like natural Hungarian")
- **Why:** the first version kept calques of the English analysis terms. Examples: "kar" for *lever*, "hatás-mérleg" for *impact ledger*, "hibarés", "divíziótársak", "csempe", "zsugorított arány", "KI", "%-pont". The user found "kar" incomprehensible.
- **Terms now used:**
  - fejlesztési lehetőség (lever) · a lehetőségek rangsora (ledger) · plusz győzelem (extra wins);
  - hibátlan futam (clean heat; "tiszta idő" stays, as it is the official term) · a divízió többi csapata (peers);
  - korrigált arány (shrunken rate) · jellemző idő (median) · összevethető futás (adjusted run);
  - visszatartott váltás (held pass) · magasságadó kutya (height dog) · legjobb négyes (A-team) · Teendők (action plan).
- **Number formats:**
  - CIs are a plain bracketed range, "(20–33)", explained once in every slide footer;
  - "százalékpont" replaces "%-pont";
  - new `nounit` and `as_pct` modifiers let the text inflect numbers correctly ("16 százalékponttal", "0,05 mp-nél", "77%-át").
  - Corrected several wrong suffixes after units (e.g. "mp-nál" → "mp-nél").
- **Jargon:** moved out of the talk slides into the speaker notes or the appendix (pszeudo-R², AUC, Spearman).
- **Charts, tables and site:**
  - chart labels, table headers, the site template and script, and the line-up presets were all reworded;
  - the CSV downloads now have Hungarian column names and values (category, breed), and use `;` and a decimal comma, as Hungarian Excel expects;
  - the ledger download was renamed `lehetosegek_rangsora.csv`, and stale downloads are now cleared on each build.
- **No number changed.** All 113 tests pass. The site was rechecked in headless Chromium: no errors, no overflow at 390 px, and the builder still gives 19,28 mp for the best four.

### 7.9 Explaining the weak fault prediction (user question)
- **Question:** the user asked whether AUC 0.55 means the result is practically a random guess.
- **Answer:** yes, for a single heat; no, for the season-level recommendations. Per-heat fault outcomes are mostly random. The differences in fault rate between dogs are real and add up over a season (e.g. Cookies 37 % false starts, CI 25–51, against Enola's 10 %).
- **Added to the deck:**
  - methods slide: a plain bullet stating this;
  - methods notes: the loaded-coin analogy;
  - running-order notes: the recommendation promises fewer false starts per season, not a clean heat;
  - back-test appendix notes: the same point.
- **New derived numbers** (from `lineup_backtest.csv`):
  - `backtest_clean_heats`: 214 autumn heats;
  - `backtest_p_clean_predicted` 56 % vs `backtest_p_clean_observed` 64 %. The teams were cleaner in autumn, so the spring–summer fault rates are, if anything, pessimistic.

## Step 8 – Preparing the public GitHub release (2026-10-14)
- **Privacy check:** scanned every file to be published, and the git history, for secrets, emails, local paths and document metadata. No secrets or local paths were found.
- **One source-file edit (user decision):** `FLYBALLCZ_versenyadatok.xlsx` carried the data provider's personal Gmail address in its document properties (author and last-modified-by). Both fields were blanked. This is the only change ever made to a source Excel file: every sheet and all other parts of the file are byte-identical. Rebuilding with `run_phase2_clean.py` gives identical `runs`/`heats` tables and CSVs, and all 113 tests pass.
- **Kept as-is (user decision):** the masked handler IDs and chip numbers in the dog master data, and the Mac folder path stored in the FLYBALLCZ workbook.
- **`data/processed/` is now committed**, so the cleaned tables can be used without rerunning the pipeline.
- **History:** the repo was restarted as one commit with no history, so the old copy of the Excel file with the address is not published.
