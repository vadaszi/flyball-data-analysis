# WRFT Flyball Analysis – Project Guide

Data-analysis project for the coach of the fictional Wild Runners Flyball Team (WRFT): analyse the 2023 competition results and deliver code plus a business presentation (PDF).

## Read first
| File | Content |
|---|---|
| `flyball_elemzes.md` | The brief (Hungarian): questions, deliverables, scoring |
| `WRFT_dokumentacio.md` | Client's data dictionary |
| `data_structure.md` | **Physical Excel layout, hidden font-colour encodings, per-sheet facts, known anomalies.** Read this before writing any loader |
| `domain_knowledge.md` | Flyball rules (FCI/UKFL), terminology mapping, benchmarks, and implications for cleaning and analysis |
| `ANALYSIS_LOG.md` | Working log of every step done on the data |

## Rules for working in this project
- **Log every step** in `ANALYSIS_LOG.md`: what was done, why, and how many rows or values it affected. Entries can be written whenever convenient; what matters is that the log is complete and consistent with the outputs by the end of each phase. Never put the log in this file.
- **Never modify the source Excel files.** All cleaning happens in code. (Single exception, 2026-10-14: the provider's email was blanked from the FLYBALLCZ file's document properties before the public release; the data is unchanged. See `ANALYSIS_LOG.md` Step 8.) Outputs go to `data/processed/`.
- **Work phase by phase** following the brief: (1) exploration → (2) cleaning → (3) basic analyses → (4) advanced analyses (correlations, per-competition, weather) → (5) synthesis → (6) visualisation and presentation. **Wait for the user's go-ahead before starting each phase.**
- Analysis documents are in English; the presentation and the website (Phase 6) are in Hungarian, at the user's request.
- The user doesn't review code but asks for explanations. Keep the code readable and modular, and keep the log explanations plain.
- The Linux box is a sandbox: install what is needed in a project virtual environment. Fetching weather data from the web is allowed (Open-Meteo historical API planned).

## Planned layout
- `src/`: Python modules (load, clean, weather, analysis, plots)
- `notebooks/`: narrative notebooks that call `src/`
- `data/processed/`: cleaned tables
- `figures/`: charts
- `reports/`: presentation

## Status
- **Phase tracker: `plan.md`.** It holds per-phase checklists and session handoff notes. Read it first in every new session.
- 2026-10-13: Exploration and domain research done. Created `data_structure.md`, `domain_knowledge.md` and `ANALYSIS_LOG.md` (Step 0).
- 2026-10-13: Planning done. Created `plan.md`; the project is a local git repo, with a commit at the end of each phase.
- 2026-10-13: Phase 2 (cleaning) done. `uv run python scripts/run_phase2_clean.py` rebuilds `data/processed/`; `uv run pytest` runs 62 tests. Details in `ANALYSIS_LOG.md` Step 1.
- 2026-10-13: Phase 3 (basic analyses) done. `uv run python scripts/run_phase3_basic.py` rebuilds `reports/phase3/`, `reports/dog_scorecards.csv` and `figures/phase3/`; `uv run pytest` runs 74 tests. Details in `ANALYSIS_LOG.md` Step 2.
- 2026-10-13: Phase 4.0 (weather data) done. `uv run python scripts/run_phase4_weather.py` rebuilds `weather_hourly.csv`, `weather_day.csv` and `heat_weather.parquet` from the committed Open-Meteo cache in `data/external/weather/`; `uv run pytest` runs 84 tests. Venue picks are in `config.VENUES`. Details in `ANALYSIS_LOG.md` Step 3.
- 2026-10-13: Phase 4A (Q1 lane, Q2 sex/neuter, Q3 per competition) done. `uv run python scripts/run_phase4a.py` rebuilds `reports/phase4a/` and `figures/phase4/`; `uv run pytest` runs 92 tests. Details in `ANALYSIS_LOG.md` Step 4.
- 2026-10-13: Phase 4B (weather analysis, ideal line-up) done; Phase 4 complete. `uv run python scripts/run_phase4b.py` rebuilds `reports/phase4b/` and 6 figures in `figures/phase4/`; `uv run pytest` runs 100 tests. Details in `ANALYSIS_LOG.md` Step 5.
- 2026-10-13: Phase 5 (synthesis) done. `uv run python scripts/run_phase5_synthesis.py` rebuilds `reports/phase5/` (impact ledger + `key_numbers.json`); the written deliverables are `reports/findings.md` and `reports/storyline.md`; `uv run pytest` runs 106 tests. Details in `ANALYSIS_LOG.md` Step 6.
- 2026-10-13: Phase 6 (presentation) done; all phases complete. `uv run python scripts/run_phase6_presentation.py` rebuilds the upload folder `prezentacio/`: the Hungarian deck PDF (35 slides), the speaker notes, the interactive site `index.html` and CSVs. Slide text is in `src/flyball/report/text_hu.toml`, with numbers as `{key}` placeholders (never type numbers in). `uv run pytest` runs 113 tests. Headless Chromium needs the libraries in `~/.local/share/chromium-deps/`. Details in `ANALYSIS_LOG.md` Step 7.
- Never create `.yaml`, `.yml` or `.env` files (global rule: they can't be read). Use TOML, JSON or Python for config.
- Environment: `uv` project (`pyproject.toml`, `uv.lock`, `.venv`); run everything with `~/.local/bin/uv run …`. pandas 3.0, so strings use the `str` dtype.
- Key cleaning facts: lane colour = font colour of the team-name cell; identify WRFT dogs only inside `WildRunners*` team rows; 19 rows are shifted one cell after a `vběhl` in a changeover cell (repaired in `parse.realign_shifted_row`); the Czech championship was on 2–3 Sep 2023, not 3–4; `ok` passes are a censored "< ~0.08 s" value (medians fine, means need imputation); peers = competition × division. Full list in `ANALYSIS_LOG.md` Step 1, `domain_knowledge.md` §10 and `data_structure.md`.
