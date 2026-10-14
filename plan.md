# WRFT Flyball 2023 – Project Plan and Phase Tracker

This file tracks progress phase by phase, so any new session can pick up where the last one stopped. Tick the boxes as tasks are done. Fill in **Session handoff** at the end of every session.

- Brief: `flyball_elemzes.md`
- Data and domain references: `data_structure.md`, `domain_knowledge.md`
- Step-by-step data log: `ANALYSIS_LOG.md`

---

## Goal
The coach of the Wild Runners Flyball Team (WRFT) wants their 2023 season analysed:

- **General picture:** start, run and changeover times, and faults, for teams and dogs.
- **Q1:** Does **lane colour** (red/blue) significantly affect dog performance?
- **Q2:** Does it matter whether a dog **passes onto an intact or neutered male or female**?
- **Q3:** Every analysis broken down **per competition** (venue and date).
- **Extra:**
  - attach **weather** data to every competition;
  - test the coach's weather hypothesis (temperature, wind, humidity, rain);
  - recommend the **ideal team line-up**.

**Deliverables:** code (`.py` and `.ipynb`) and a **PDF** presentation for a 10–12 minute business talk.

**Scoring:**
- Business value: 50 points
- Coding: 30 points
- Visualisation: 20 points

## Decisions (2026-10-13)
- Slides are built by code: HTML/CSS → PDF. Slide text lives in a separate file, so a Hungarian version can be swapped in.
- Local git, with one commit at the end of each phase. Nothing is pushed.
- Deliverables in English first.
- Wait for the user's go-ahead before each phase.
- Every data step is logged in `ANALYSIS_LOG.md`.
- **No `.yaml`, `.yml` or `.env` files** anywhere in the project. Config goes in `pyproject.toml` or in Python, JSON or TOML files.

## Conventions

### Environment
A `uv` project (`pyproject.toml`, `.venv`). Run commands with `~/.local/bin/uv run …`.

### Code layout
```
src/flyball/     config.py · excel_reader.py · parse.py · dogs.py · clean.py · metrics.py
                 stats.py · weather.py · lane.py · partner.py · competition.py · weather_effects.py
                 lineup.py · synthesis.py · plots/ (style.py + phase3.py, …) · report/
scripts/         run_phase2_clean.py, run_phase3_basic.py, … (one per phase, re-runnable)
notebooks/       02_cleaning.ipynb … 06_presentation.ipynb (narrative; they call src/)
tests/           parser and invariant tests
data/processed/  cleaned tables
data/external/   weather cache
figures/         charts
reports/         findings, presentation
```

### Source data
The source Excel files stay in the project root, read-only.

### Statistical standards
- **Repeated measures:** each dog runs many times, so use mixed models with the dog as a random effect, or cluster-robust GEE.
- **Faulted runs:** left out of speed metrics, but analysed separately.
- **Break-out rule:** lower divisions may hold back speed deliberately, so compare speed **within a division**.
- **Reporting:** give effect sizes with 95% CIs, not just p-values.
- **Multiple tests:** apply a Holm or BH correction.
- **"No effect" claims:** back them with an equivalence test (TOST).
- **Exclusion rules:** run a sensitivity check for each one.

### End of every phase
1. Log entries are complete.
2. Boxes are ticked here and the handoff is written.
3. The status in `CLAUDE.md` is updated.
4. Git commit.
5. Short plain-language summary for the user, then wait.

---

## Phase 0 – Planning and setup ✅
- [x] Read the brief and the reference docs; write this plan
- [x] `git init`, `.gitignore`, first commit
- [x] `CLAUDE.md` points to this file

## Phase 1 – Exploration ✅ (Step 0 in the log)
- [x] Data inventory, hidden font-colour encodings, day split, anomalies (`data_structure.md`)
- [x] Domain research and its implications (`domain_knowledge.md`)

## Phase 2 – Data cleaning ✅ (Step 1 in the log)
**Goal:** reproducible tidy tables plus a data-quality report. Every rule is logged with the number of rows it affects.

- [x] **Setup:** `uv` package project (`src/flyball/`), dependencies installed, `uv.lock` committed.
- [x] **`excel_reader.py`:** reads A–T by position; lane and red-font fault flags resolved through each file's own colour palette. Skips blank rows (Eager's Cup has a blank row at the day break) and stops after 20 in a row.
- [x] **`parse.py`:** titles, day split (asserts one overnight drop), time-cell codes, rounding to 3 dp. **New:** `realign_shifted_row` repairs 19 rows shifted one cell after a `vběhl` in a changeover cell; this explains all negative run times.
- [x] **`dogs.py`:** dates, 4 ulna fixes, `breed_group`, `category`, FCI-height check, age helper.
- [x] **`clean.py`:** `competitions.csv` (28 sheet-days), `heats.parquet` (8,571 rows / 4,336 heats / 1,172 races), `runs.parquet` (33,904 dog slots), plus `dogs.csv`, `data_quality.csv` and `wrft_hurdle_check.csv`.
- [x] **Exclusion flags:** practice (28), zero total (17), dog "0" (14), runs < 3.3 s (16), > 10 s (23), per-dog outliers (249), passes > 3 s (213) → `valid_speed` and `valid_pass`.
- [x] **Validation:**
  - hurdle check (systematic per-dog differences → the heat hurdle is authoritative)
  - Hank and Bonnie under 18 months
  - Abby ran for 2 WRFT teams on one day
  - **Czech championship moved to 2–3 Sep 2023**, verified online
- [x] **Tests:** 62 pass. Identity tolerance is ±0.04 s (8 parts rounded to 0.01 s), giving **88.9 %**, not 87.7 %.
- [x] **Outputs:** `scripts/run_phase2_clean.py`, `notebooks/02_cleaning.ipynb`, spot-check of 6 rows (all match).

## Phase 3 – Basic analyses ✅ (Step 2 in the log)
**Goal:** the coach's "general picture". The focus is WRFT, with the whole field (about 8,500 rows) as the benchmark.

- [x] **Define a "good result":** a **won heat**; its levers are (1) a clean heat, (2) a faster clean time than the division peers.
  - Heat-win model: logistic regression with **cluster-robust SEs on race** instead of a team random effect. statsmodels has no frequentist mixed logistic model, and WRFT has only 7 teams (too few clusters).
  - Who faulted explains about 15× more than typical speed (pseudo-R² 0.25 vs 0.02, field).
- [x] **Team level** (7 WRFT teams vs the field, compared within **competition × division**, Holm over 42 tests):
  - win rate, clean time, start and pass profiles, fault rate by type
  - cost of faults: 155 WRFT losses (23.5 %) avoidable; a corrected false start or early pass costs ~8 s
- [x] **Dog level** (50 WRFT dogs): `reports/dog_scorecards.csv` with Wilson CIs and empirical-Bayes shrunken rates; mixed-model position and hurdle effects (hurdle step ≈ 0.02 s per dog per run)
- [x] **Starts and passes:** passes tighter than ~0.12 s don't pay; the best starters are also the safest. `ok` turned out to be a censored "< ~0.08 s" code (log 2.2).
- [x] **Outputs:** `metrics.py`, `stats.py`, `plots/`, `scripts/run_phase3_basic.py`, `notebooks/03_basic.ipynb`, `reports/phase3/*.csv`, 6 draft figures in `figures/phase3/`, 12 new tests (74 in total)

## Phase 4 – Advanced analyses
Three sessions, in this order (decided 2026-10-13):
- **4.0:** weather data: fetch and attach it (data preparation, before any analysis)
- **4A:** Q1, Q2, Q3 (Q3's per-competition view includes the weather columns)
- **4B:** weather analysis and line-up

**Why weather data comes first:** it is a data step like cleaning, and Q3 needs it ("attach weather data to every competition"). Venue ambiguity may need the user's input, and the external API is the main outside risk, so it is cleared early. The weather *analysis* stays in 4B; Q1 and Q2 don't need weather (their models already compare within the same competition day).

- [x] **4.0 Weather data** ✅ (log Step 3; `src/flyball/weather.py`, `scripts/run_phase4_weather.py`, `notebooks/04_0_weather.ipynb`)
  - [x] Venues geocoded and ambiguous ones resolved from the events' own pages (Heroltice = Brno-venkov, Louňovice = Praha-východ, Pláně = Plzeň-sever, Blšany = Louny-district football ground); coordinates fixed in `config.VENUES`.
  - [x] 11 Open-Meteo archive requests (event days + day before), raw JSON cached and committed in `data/external/weather/`.
  - [x] Joined at heat minute: instantaneous variables interpolated, rain/gust/radiation from the containing hour block, plus 3 h / 24 h rain. All 4,336 heats matched; `weather.attach()` for heats/runs.
  - [x] Outputs: `weather_hourly.csv`, `weather_day.csv`, `heat_weather.parquet`, draft `figures/phase4/weather_strip.png`; 10 new tests (84 total); station spot-check (temperature r 0.93–0.98, rain unreliable → use as dry/wet).

- [x] **4a. Q1 – lane colour** ✅ (log 4.1–4.2; `lane.py`): no effect that matters. Field blue +0.006 s/run (real but negligible); per ring-day ≤ 0.032 s; lanes drawn per race (first-listed team = blue).
  - Model: mixed model `log(run_time) ~ lane + position + hurdle + division + (1|dog) + (1|ring-day)`.
  - Fit it twice: on all dogs, and on WRFT dogs only.
  - Compare the lanes on start time, pass time and fault rate as well.
  - Check how lanes are assigned: do teams alternate between heats?
  - Allow a separate lane effect per ring, to catch asymmetries at specific venues.
  - Equivalence test (TOST) at ±0.05 s.
- [x] **4b. Q2 – passing onto intact/neutered male/female** ✅ (log 4.3; `partner.py`): no measurable effect on racing passes or runs; lead: passes onto intact males held back +11 pp. Added: age/team-adjusted spec (intact dogs are young) and the split into racing pass time + held-pass rate.
  - Data: WRFT dogs only, positions 2–4.
  - Outcomes for the outgoing dog: pass time, early-pass rate and run time.
  - Main predictor: the category of the incoming dog.
  - Controls: the dog itself, as a random effect; its own category; its position.
  - Also test the sex × sex interaction.
  - Intact females are only 2 dogs: show honest CIs and test with merged categories as a sensitivity check.
- [x] **4c. Q3 – per competition** ✅ (log 4.4; `competition.py`): 20 WRFT competition days with results, peers, dog-adjusted speed index, lane and weather; season trend −0.29 %/month (WRFT).
  - Every Phase 3 metric broken down by competition, date, ring and day.
  - Season trend over the year.
  - Figures: small multiples and a heatmap.
- [x] **4d. Weather analysis** ✅ (log 5.1–5.6; `weather_effects.py`): only **heat above 20 °C** matters, at +0.083 s per dog run per 10 °C (+1.9 %). Humidity, wind and rain are too small to matter for speed; faults are inconclusive.
  - Main model: within competition (dog × event absorbed), clustered on venue-day, t(21).
  - Checks: within-day model, WRFT mixed model, a day-level meta-regression (weather + season R² 0.77), 20 sensitivity variants, and a GBM with leave-one-competition-out CV.
  - **Added:** a second-day control. Without it, "warmer = more faults" appeared, which was really Saturday vs Sunday. Side finding: **day 2 has +19 pp clean heats**.
- [x] **4e. Ideal line-up** ✅ (log 5.7–5.10; `lineup.py`): **A-team Maggie > Enola > Pax > Alfie** (19.3 s expected, 16.6 s without faults).
  - Pool: 42 dogs with ≥ 20 runs (user decision).
  - Exhaustive search: 2.7 M ordered line-ups.
  - Current teams: Hopefuls gain 2.2 s by starting Maggie instead of Cookies; XXL and Zephyr gain 1.0–1.3 s from the order alone.
  - Height dog: no small dog pays off in a top team.
  - Back-test: Spearman 0.91; the model beats a naive baseline at unusual heights only.
  - Stability: core Enola, Alfie, Maggie.
- [x] **Outputs:** `weather_effects.py`, `lineup.py`, `stats.py` helpers, `scripts/run_phase4b.py`, `notebooks/04b_weather_lineup.ipynb`, `reports/phase4b/` (29 tables), 6 figures in `figures/phase4/`, 8 new tests (100 total)

## Phase 5 – Synthesis ✅ (Step 6 in the log)
**Decisions (2026-10-13):** rank the findings with a computed **impact ledger** (not by judgement); the storyline is a **Markdown outline**, and Phase 6 turns it into the slide-text file.

- [x] **Impact ledger** (`synthesis.py`): every lever in **extra heats won per season** against other clubs (907 heats, WRFT won 39.0 %), via the Phase 3 WRFT heat-win model; 2,000 coefficient draws for CIs; 39 levers.
  - Saturday as clean as Sunday +28; all recommended running orders +27 (free, now); every fault gap to peers +26; Pax swaps +3 to +45 (one team only, optimistic); heat ≤ +3.5; ceiling (no own faults) +148.
  - Line-up levers compare two model arms (current vs recommended) against the opponents of the team's last competition (log 6.3).
- [x] **Key numbers:** `reports/phase5/key_numbers.json` (97 numbers with unit, CI, source, log step), the single source for findings and slides.
- [x] `reports/findings.md`: 9 findings ranked by impact, each with evidence, effect size, confidence, **action for the coach** and a check for next season, plus the action plan, open questions and limitations.
- [x] `reports/storyline.md`: 13 main slides (~12 min) with action titles, key-number keys, visuals and speaker notes, plus the appendix and the list of charts Phase 6 must build.
- [x] Consistency audit: all phase scripts reproduce the committed outputs byte for byte.
- [x] **Outputs:** `scripts/run_phase5_synthesis.py`, `notebooks/05_synthesis.ipynb`, `reports/phase5/` (4 files), 6 new tests (106 total), `lineup.score_line_ups` helper

## Phase 6 – Visualisation and presentation ✅ (Step 7 in the log)
**Decisions (2026-10-13):** Hungarian only; one PDF with the talk part plus a detailed appendix; an interactive website; everything in one upload folder, `prezentacio/`, where the site links to the PDF.

- [x] Loaded the `dataviz` skill; kept the Phase 3 colour roles (red/blue = lanes only, violet = WRFT, grey = field, aqua/orange = good/fault).
- [x] **Numbers:** `report/numbers.py` resolves `{key|modifiers}` placeholders from `key_numbers.json`, plus 40 derived numbers and per-dog lookups, in Hungarian format. A test forbids typed-in numbers.
- [x] **Text:** `report/text_hu.toml` holds every slide, the speaker notes, the glossary and the site text.
- [x] **Charts:** `plots/deck.py`, 27 SVGs in `figures/phase6/`.
  - New: season calendar, heat-strip timeline, impact ledger with the "you are here" strip, Saturday/Sunday slope, stability bars, per-competition panels, team gaps, heat-model forest plot.
  - Redrawn in Hungarian: the Phase 3–4 drafts.
  - Line-up cards and the A-team card are built in HTML.
- [x] **Deck:** 35 slides (15 for the talk, 12:00 by the slide timings, then 20 in the appendix), Jinja2 → headless Chromium → `prezentacio/WRFT_2023_elemzes.pdf`, plus a speaker-notes PDF.
- [x] **Website:** `prezentacio/index.html`, offline-capable. It has:
  - an interactive ledger and dog quadrant (Vega-Lite);
  - a clickable season calendar and a competition-day explorer;
  - a **line-up builder** (a JS port of `score_orders`, parity-tested under Node);
  - a sortable dog table;
  - CSV downloads.
- [x] **QA:** every slide and the site (1280 px and 390 px) rendered and inspected; no console errors; byte-identical rebuilds.
- [x] **Outputs:** `scripts/run_phase6_presentation.py`, `notebooks/06_presentation.ipynb`, `tests/test_phase6.py` (7 tests, 113 in total).
- [ ] Optional later: English version (`text_en.toml` plus the chart labels).

## Verification (every phase)
- `uv run pytest` passes.
- `uv run python scripts/run_phaseN_*.py` regenerates all outputs from the raw Excel files.
- The notebooks run cleanly with `jupyter nbconvert --execute`.
- Results are spot-checked by hand against the Excel.

---

## Session handoff
*Newest entry at the top. At the end of each session, record what was done, what is open, and what comes next.*

### 2026-10-13 – Phase 6 (presentation) session
- **Done:** Phase 6 complete, so all phases are complete. See `ANALYSIS_LOG.md` Step 7.
  - `uv run python scripts/run_phase6_presentation.py` rebuilds `prezentacio/` and `figures/phase6/` in about 7 s (it needs the Phase 2–5 outputs).
  - 113 tests.
- **The deliverable folder `prezentacio/`:**
  - `index.html` (interactive site);
  - `WRFT_2023_elemzes.pdf` (35 slides);
  - `WRFT_2023_eloadoi_jegyzet.pdf` (speaker notes);
  - `adatok/*.csv`;
  - `assets/`;
  - `OLVASS_EL.md` (how to upload).
- **Corrections:** the weather sensitivity analysis has 20 variants, not 22 (findings, storyline and plan fixed; log 7.4).
- **Machine note:** headless Chromium needs three libraries that were installed without root in `~/.local/share/chromium-deps/` (log 7.1).
- **Open:** an English version if wanted. To change slide text, edit `text_hu.toml` and rerun the script.

### 2026-10-13 – Phase 5 (synthesis) session
- **Done:** Phase 5 complete. See `ANALYSIS_LOG.md` Step 6.
  - `uv run python scripts/run_phase5_synthesis.py` rebuilds `reports/phase5/` in about 25 s (needs the Phase 3–4 outputs).
  - `notebooks/05_synthesis.ipynb` is the walk-through.
  - 106 tests.
- **Decisions this session:**
  - Ranking by a computed impact ledger (extra heats won per season). The storyline is a Markdown outline.
  - Line-up levers are scored as two model arms against the last competition's opponents (the first version overstated Zephyr's swap; log 6.3).
  - Start and pass seconds count through the speed term.
- **Key results for Phase 6:**
  - The one message: **fast enough, losing on faults.**
  - The three levers are each worth about 27 heats a season: the running order (free, now), Saturdays (cause unknown), and the fault gaps (training).
  - Planning target: about +5 pp of win rate (a judgement; the levers overlap).
  - The deck reads every number from `key_numbers.json`. `storyline.md` lists the keys per slide and the new charts to build: season calendar, heat-strip timeline, impact-ledger bars with a "you are here" strip, line-up cards, Saturday/Sunday slope chart.
- **Open questions for the coach** (unchanged; now in findings.md): Pax's availability, what differs on Saturdays, Maggie as starter, held passes onto intact males, indoor events.
- **Next:** Phase 6 (visualisation and presentation). Waiting for the user's go-ahead.

### 2026-10-13 – Phase 4B (weather analysis, line-up) session
- **Done:** 4B complete, so Phase 4 is complete. See `ANALYSIS_LOG.md` Step 5.
  - `uv run python scripts/run_phase4b.py` rebuilds `reports/phase4b/` (29 tables) and 6 figures in about 55 s.
  - `notebooks/04b_weather_lineup.ipynb` is the walk-through.
  - 100 tests. scikit-learn added.
- **Decisions this session:**
  - The line-up pool is every dog with ≥ 20 valid runs (42). The GBM check is included.
  - `day2` became a standard control.
  - Swaps use bench dogs only.
  - The line-up height is the typical raced height, not the lowest.
- **Key findings for Phase 5:**
  - **Heat:** +0.08 s per run per 10 °C above 20 °C (about 0.3 s per heat on a 30 °C day). It is the only weather factor that matters for speed.
  - **Second day of an event: +16–19 pp clean heats**, with fewer false starts and early passes, for the same teams. This is the biggest controllable lever found in 4B; the cause is unknown.
  - **Line-up:** A-team Maggie > Enola > Pax > Alfie. Maggie as starter rests on 14 starts; Enola first is the proven option (0.5 s worse in expected time).
  - **Order matters:** Hopefuls −2.2 s by not opening with Cookies (34 % false starts).
  - **Height dog:** none of WRFT's small dogs pays off for a top team.
  - **Confidence:** the speed model is good at ranking (0.91), weak on faults (AUC 0.55). The exact A-team is not stable, but the core is.
- **Open questions for the coach:**
  - Is Pax still available (last raced July)?
  - What happens differently on Saturdays?
  - Is Maggie trainable as a starter?
- **Next:** Phase 5 (synthesis: `reports/findings.md`, storyline). Waiting for the user's go-ahead.

### 2026-10-13 – Phase 4A (Q1, Q2, Q3) session
- **Done:** 4A complete. See `ANALYSIS_LOG.md` Step 4. `uv run python scripts/run_phase4a.py` rebuilds `reports/phase4a/` (16 tables) and 5 figures in `figures/phase4/` in about 55 s; `notebooks/04a_questions.ipynb` is the walk-through; 92 tests.
- **Key findings for later phases:**
  - **Q1:** lane colour doesn't matter (TOST at ±0.05 s passes everywhere). One slide is enough; lanes can be ignored in 4B models.
  - **Q2:** no sex/neuter effect on racing performance; the intact categories are young dogs (age confound) and held-back passes (> 1 s) need their own treatment (`metrics.HELD_PASS_S`). Lead for the coach: passes onto intact males held back more often.
  - **4d (weather):** the dog-adjusted speed index (`competition.speed_index`) is the outcome to explain: hottest days (Máchale Sat, EFC Sat) +1.5–2.2 % slower, Budějckej (Oct) fastest, but Eager's Cup Sunday (9 °C) was not fast, so venue matters too. Fit weather + season trend + venue together; the trend (−0.29 %/month) is partly temperature.
  - **4e (line-up):** WRFT trails its peers only through faults (4 days below peers on win rate, never on clean time); Gordon's speed swings most between competitions (hurdle height changes with the team).
  - New helpers: `stats.absorbed_ols` (fast within-group FE, clustered), `stats.crossed_mixed`, `stats.tost`/`verdict`.
- **Open questions:** none blocking. For the coach: are held-back passes deliberate (e.g. with young intact males)?
- **Next:** 4B (weather analysis, ideal line-up). Waiting for the user's go-ahead.

### 2026-10-13 – Phase 4.0 (weather data) session
- **Done:** 4.0 complete. See `ANALYSIS_LOG.md` Step 3. `uv run python scripts/run_phase4_weather.py` rebuilds the weather outputs from the committed cache in about 2 s (`--refresh` re-downloads).
- **Key findings for later phases:**
  - **4c (Q3):** `weather_day.csv` has one row per `comp_day_id`, ready to join to per-competition tables.
  - **4d (weather):** use `weather.attach(runs, heat_wx)` for heat-level weather.
    - Temperature has a good spread (7–33.5 °C).
    - Rain is light and unreliable in millimetres, so use dry/wet flags and `precip_24h_mm` for ground wetness.
    - Wind is moderate (gusts ≤ 14.5 m/s), and its direction can't be related to the lanes.
    - 4 events changed sharply between Saturday and Sunday (Žamberk, Louňovice, EFC, Vodňany). A within-competition model can exploit this.
    - Temperature and season are confounded (cold days are April, May and October), so control for the date or season trend.
  - **Not known:** indoor or outdoor status (assumed outdoor) and lane orientation.
- **Open questions:** none blocking. The coach could confirm whether any event was indoors.
- **Next:** 4A (Q1 lane, Q2 sex/neuter, Q3 per competition). Waiting for the user's go-ahead.

### 2026-10-13 – Phase 3 (basic analyses) session
- **Done:** Phase 3 complete. See `ANALYSIS_LOG.md` Step 2.1–2.9. `uv run python scripts/run_phase3_basic.py` rebuilds everything in ~15 s.
- **Key findings for later phases:**
  - **4c (per competition):** `metrics.team_summary(..., group=["competition", "team"])` and `attribution_summary` already take a group argument; reuse them.
  - **4a (Q1):** `metrics.heat_view` gives both sides of each paired heat, with the opponent's columns. `ok` passes are censored, so compare lanes with medians or the `ok` share, not means.
  - **4b (Q2):** pass metrics belong to the dog entering at the pass (positions 2–4); `prev_category` is the returning dog.
  - **4e (line-up):** `adj_run_s` (shrunken dog speed at 25 cm, position 1) and `*_eb` fault rates are in the scorecards; hurdle step ≈ +0.02 s per dog per run; position 1 ≈ 0.035 s faster for the same dog. The 15 cm height dog is **Gordon** (6.9 s median), not Punk.
  - **Weather (4d):** use the competition-day fixed-effect pattern from `stats.dog_run_model` with weather terms in place of the day dummies.
- **Open questions:** none blocking.
- **Next:** Phase 4.0 (weather data), then 4A (Q1, Q2, Q3). The order was changed after this session; see the note at the top of Phase 4. Waiting for the user's go-ahead.

### 2026-10-13 – Phase 2 (cleaning) session
- **Done:** Phase 2 complete. See `ANALYSIS_LOG.md` Step 1.0–1.10 for every rule and count.
- **Key findings for later phases:**
  - **Breakouts:** 15 complete, fault-free loss/loss heats look like break-outs. This supports comparing speed within a division.
  - **Q2:** the intact-female group is 2 dogs, and one of them (Bonnie) is under 18 months.
  - **4e (line-up):** some dogs raced at a different height than the master sheet says. Use the raced height (`wrft_hurdle_check.csv`).
  - **Weather:** use the corrected Czech championship dates.
  - **Opponent dogs:** keyed `team|name`, so the same physical dog in two teams counts as two dogs.
- **Open questions:** none blocking.
- **Next:** Phase 3 (basic analyses). Waiting for the user's go-ahead.

### 2026-10-13 – Planning session
- **Done:**
  - Read the brief and the docs, and wrote this plan.
  - Initialised git.
- **Open questions:** none.
- **Next:** Phase 2 (cleaning), starting with the environment setup. Waiting for the user's go-ahead.
