# WRFT 2023: storyline for the presentation

*Phase 5 deliverable, 2026-10-13. Phase 6 turns this outline into the slide-text file and the HTML→PDF deck (`reports/WRFT_2023_analysis.pdf`).*

## Brief for the deck
- **Audience:** the WRFT coach, possibly with handlers. They know flyball well but not statistics.
- **Length:** 13 main slides in about 12 minutes (timings below), plus an appendix for questions.
- **Shape:** answer first.
  1. The one message: "fast enough, losing on faults".
  2. The common currency (heats won).
  3. The levers, biggest first.
  4. The coach's own questions.
  5. The action plan.
- **Titles are sentences.** Each slide title is the takeaway; the body proves it.
- **Numbers:** every number on a slide comes from `reports/phase5/key_numbers.json`. The keys are given per slide below.
- **Visual through-line:** the **impact-ledger bar** (slide 4) comes back as a small "you are here" strip on each lever slide (5–8), with that lever highlighted. The audience always sees where the lever ranks.
- **Colour roles** (`plots/style.py`): red and blue are reserved for lanes. WRFT is violet, the field is ink/grey, and "good" and "bad" use the diverging aqua ↔ orange scale.

---

## Main slides

### 1 · Executive summary · 1:00
**Title:** WRFT's dogs are as fast as the field; WRFT loses on faults. Three levers are each worth about 27 heats a season.
- **Numbers:**
  - `wrft_median_run_s` vs `field_median_run_s` (4.28 vs 4.27 s);
  - `wrft_win_rate` vs `field_win_rate` (40.8 % vs 45.6 %);
  - `impact_all_reorders` (+27), `impact_day2` (+28), `impact_all_fault_gaps` (+26).
- **Visual:** three "lever cards" (icon, extra wins, what it takes), plus one line answering each of Q1–Q3 and the weather.
- **Notes:**
  - Say the answer first: the speed is already there and the faults are the problem.
  - The three levers overlap and won't add up fully. Say "about +5 pp of win rate is a realistic 2024 target", not "+80 heats".

### 2 · Season at a glance · 0:45
**Title:** 20 competition days, 1,116 heats with a result, from 7 °C to 33 °C.
- **Numbers:** `wrft_competition_days`, `wrft_heats_with_result`; WRFT win and clean-heat rates.
- **Visual (new):** **season calendar**, one tile per competition day. Tile colour = WRFT clean-heat rate; a temperature strip under each tile; a marker on the 4 days below the peers. Builds on `figures/phase4/weather_strip.png` and `competition_days.csv`.
- **Notes:** set the scene: 11 events, 7 WRFT teams, 50 dogs. Weather is attached to every heat.

### 3 · What wins a heat · 1:00
**Title:** A clean heat wins 85 % of the time against a faulting opponent; a faulted heat wins 9 % against a clean one.
- **Numbers:**
  - `win_clean_vs_fault`, `win_fault_vs_clean`, `win_clean_vs_clean`;
  - `heat_model_r2_faults` vs `heat_model_r2_speed` (0.25 vs 0.017);
  - `rerun_cost_false_start_s` / `rerun_cost_pass_fault_s`;
  - `wrft_avoidable_losses` (155).
- **Visual:**
  - `figures/phase3/what_wins.png` (2×2 win-rate grid), redrawn for the deck;
  - plus a **heat-strip race timeline**: one real avoidable loss (Hopefuls at Hanácké, row 11: 16.27 s with an early pass, lost to 18.43 s), drawn as start / runs / passes / rerun on a time axis.
- **Notes:**
  - This defines the "good result": a won heat.
  - A fault costs about 8 s of rerun, more than the speed gap between almost any two teams.

### 4 · The impact ledger · 1:00
**Title:** One currency for every lever: extra heats won per season.
- **Numbers:** the ledger rows (`impact_*`), with `impact_ceiling` (+148) as the reference.
- **Visual (new):** **ranked horizontal bars with 95 % CIs**, grouped by kind:
  - free now;
  - investigate;
  - training;
  - depends on a dog;
  - welfare.

  The ceiling is drawn as a faint full-width bar; lane and partner sex appear as zero-length rows ("no effect"). This chart is reused as the through-line strip.
- **Notes:**
  - How it works, in one sentence: "we change the inputs of the heat-win model the way the lever would, and count how many more heats it predicts WRFT wins".
  - These are what-ifs, good for ranking, not promises.

### 5 · Lever: running order · 1:00
**Title:** Changing who starts wins Hopefuls, Zephyr, XXL and Maximini about 27 more heats, and costs nothing.
- **Numbers:**
  - `impact_all_reorders`, `impact_hopefuls_reorder`;
  - `hopefuls_order_gain_s`, `zephyr_order_gain_s`, `xxl_order_gain_s`;
  - `cookies_false_start_rate` with `cookies_starts`;
  - `start_fault_rate_0.05_0.08` vs `start_fault_rate_0.14_0.18`.
- **Visual:** **line-up cards**: each team's current and recommended order side by side, with the dog that moves highlighted. The expected-time bar comes from `figures/phase4/lineup_breakdown.png` (start / runs / passes / fault cost).
- **Notes:**
  - Most of the gain is the starter: Cookies false-starts 37 % of the time.
  - Fast starters are also the safest starters.
  - Maggie as the Hopefuls starter has only 14 starts, so the safe alternative is Enola.

### 6 · Lever: Saturdays · 1:00
**Title:** The same teams run 16 pp more clean heats on Sunday than on Saturday; fixing Saturday is worth about 28 heats.
- **Numbers:**
  - `day2_clean_heat_wrft`, `day2_clean_heat_field`;
  - `day2_false_start_wrft`;
  - `day2_run_time_field_s` (speed unchanged);
  - `impact_day2`.
- **Visual (new):** a **slope chart**, day 1 → day 2 clean-heat rate per WRFT team and event, with the field as a grey band. The speed index (unchanged) is a small inset.
- **Notes:**
  - It is not speed, it is nerves or routine; the cause is unknown.
  - Ask the coach what differs on Saturdays.
  - The proposal is an experiment: give Saturday the Sunday routine.

### 7 · Lever: fault habits · 1:15
**Title:** Each team has one fault habit to train away: XXL starts, Zephyr runs, Hopefuls passes.
- **Numbers:**
  - `xxl_false_start_gap`, `zephyr_run_fault_gap`, `hopefuls_early_pass_gap`;
  - `scotty_false_start_rate`, `ted_run_fault_rate`, `moon_early_pass_rate`, `bree_early_pass_rate`;
  - `impact_all_fault_gaps`, `impact_false_start_gaps`;
  - pass window: `pass_fault_rate_under_0.08`, `pass_fault_rate_0.25_0.35`.
- **Visual:**
  - a **speed-vs-reliability quadrant** of WRFT dogs (`figures/phase3/dog_quadrant.png`, redrawn) with the named dogs labelled;
  - a small **pass-window** panel (`figures/phase3/pass_window.png`): tighter than 0.12 s doesn't pay.
- **Notes:**
  - Name the dogs, but frame it as training targets, not blame.
  - Passes: WRFT's 0.20 s median is already in the safe window, so don't chase tighter passes.

### 8 · Line-up composition · 1:00
**Title:** Build the top team around Enola, Alfie and Maggie; Pax completes the A-team, and a height dog doesn't pay.
- **Numbers:**
  - `a_team`, `a_team_expected_s`, `a_team_no_fault_s`, `a_team_p_clean`, `lineup_orders_searched`;
  - `stability_enola`, `stability_alfie`, `stability_maggie`, `stability_pax`;
  - `easy_height_dog_net_s`, `gordon_height_dog_net_s`;
  - `impact_hopefuls_swap`, `impact_zephyr_swap` (optimistic).
- **Visual:**
  - an **A-team card** (4 dog tiles in running order, each with run, start or pass, and fault risk);
  - a **stability bar** (share of resamples);
  - `figures/phase4/height_dog_tradeoff.png` as a small panel.
- **Notes:**
  - 2.7 M line-ups were searched.
  - The core is stable; the fourth dog depends on the data.
  - Open question: is Pax available?
  - Back-test: the model ranks real line-ups correctly (Spearman 0.91).

### 9 · Q1 and Q2 · 1:00
**Title:** Lane colour and the partner's sex or neuter status don't change performance.
- **Numbers:**
  - `lane_field_s`, `lane_wrft_s`, `lane_ring_day_max_s`, `lane_ring_days`;
  - `held_pass_intact_male` (lead), `intact_female_dogs`.
- **Visual:**
  - left: **lane slope chart** of WRFT dogs, red vs blue (`figures/phase4/lane_wrft_dogs.png`), with the ±0.05 s equivalence band;
  - right: **forest plot** of the partner categories (`figures/phase4/partner_forest.png`, simplified to racing pass time and held-pass rate).
- **Notes:**
  - Answer both questions directly: "no".
  - Explain equivalence in one sentence: "we proved the lane difference is smaller than 0.05 s, not just that we couldn't find one".
  - Q2 is "no evidence" because the intact groups are tiny (2 females).
  - The lead: held passes onto young intact males.

### 10 · Weather · 0:45
**Title:** Only heat above 20 °C slows the dogs, by 0.08 s per run per 10 °C, and it slows the opponents too.
- **Numbers:**
  - `heat_run_s`, `heat_run_pct`;
  - `humidity_run_s`, `wind_run_s`, `rain_run_s`;
  - `weather_day_r2`, `impact_heat`, `fatigue_run_s`.
- **Visual:**
  - `figures/phase4/heat_curve.png` (flat to 20 °C, then rising), redrawn;
  - a 4-row verdict strip: temperature supported above 20 °C; humidity, wind and rain refuted.
- **Notes:**
  - The coach's hunch is partly right.
  - Heat matters for welfare more than results (≤ 3.5 heats).
  - Hot-day protocol above about 22 °C.

### 11 · Q3 – Competitions · 0:45
**Title:** WRFT's bad days were fault days: it fell behind its peers on 4 of 20 days, never on speed.
- **Numbers:** `wrft_competition_days`; the 4 days below the peers (`competition_days.csv`); `speed_index_field_min_pct` / `speed_index_field_max_pct`; `season_trend_wrft_pct`.
- **Visual:** `figures/phase4/competition_days.png` (small multiples per competition day) or the season-calendar heatmap from slide 2, with faults by type.
- **Notes:**
  - The full per-competition tables are in the appendix and the CSVs.
  - After each event, review the clean-heat and fault table, not just the times.

### 12 · Action plan · 1:00
**Title:** Nine actions, one KPI each. Start with the running order at the next competition.
- **Numbers:** the KPI baselines (`wrft_false_start_heats`, `day2_clean_heat_wrft`, `cookies_false_start_rate`, `xxl_false_start_gap`, `ted_run_fault_rate`), as in the findings action table.
- **Visual:** the action table from `reports/findings.md`: what · who · when · KPI · 2023 → target. Rows are tagged "now / next event / off-season".
- **Notes:**
  - End with the open questions for the coach (Pax, Saturdays, Maggie as starter, held passes, indoor events).

### 13 · Methods and limitations · 0:30
**Title:** How far to trust this.
- **Content:**
  - the data: 8,543 team rows from 28 sheet-days, cleaned and logged;
  - the models: mixed models and within-dog comparisons; Holm/BH corrections; equivalence tests;
  - weather: Open-Meteo reanalysis;
  - what-ifs: observational, so they rank the levers rather than promise results;
  - small WRFT numbers: field-wide estimates were used where possible.
- **Notes:** one breath. Point to the appendix.

---

## Appendix slides (for questions)
1. **Data and cleaning:** sources, the hidden font-colour encodings, the 19 shifted rows, exclusion rules with counts (log Step 1).
2. **Heat-win model:** the odds ratios (`phase3/heat_win_model.csv`); speed vs faults pseudo-R².
3. **Impact-ledger method:** thinning, reference arms for line-ups, the CI draws, the WRFT-vs-WRFT exclusion, the hand checks (notebook 05 §2).
4. **Team scorecards:** the 7 teams vs their peers (`peer_benchmark.csv`, Holm).
5. **Dog scorecards:** a table of the 42 pool dogs (`dog_scorecards.csv`).
6. **Q1 details:** lane by ring-day forest plot (`lane_ring_days.png`); lane assignment.
7. **Q2 details:** both specifications, the sensitivity variants, the age confound.
8. **Q3 table:** the per-competition-day table with weather (`competition_days.csv`).
9. **Weather robustness:** 20 sensitivity variants; within day; the GBM check (`weather_forest.png`, `weather_vs_venue.png`).
10. **Line-up back-test:** `lineup_backtest.png`; reserves; the speed-only search (Moon).

## Charts Phase 6 still has to build
- Season calendar (slides 2, 11)
- Heat-strip race timeline (slide 3)
- Impact-ledger bars and the "you are here" strip (slides 4–8)
- Line-up cards and the A-team card (slides 5, 8)
- Saturday/Sunday slope chart (slide 6)
- Redrawn deck versions of the Phase 3–4 drafts (slides 3, 7, 9, 10)
