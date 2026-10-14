# WRFT 2023 season: findings and actions

*Phase 5 synthesis, 2026-10-13. Every number comes from `reports/phase5/key_numbers.json` or the result table named next to it. Method details are in `ANALYSIS_LOG.md`, with step numbers in brackets, e.g. [2.4].*

---

## Executive summary

**WRFT's dogs are as fast as the field. WRFT loses heats on faults.** WRFT dogs run a median 4.28 s, the field 4.27 s, yet WRFT wins 40.8 % of its heats and the field 45.6 %. 62 % of WRFT's losses include its own fault, and 155 losses (23.5 %) were heats WRFT would normally have won [2.4]. Who faults explains the heat result about 15× better than typical speed [2.3].

To compare every lever in one currency, the impact ledger converts each one into **extra heats won per season** against other clubs. WRFT ran 907 such heats in 2023 and won 39.0 % of them [6.1]:

| # | Lever | Extra wins per season (95 % CI) | Win rate | What it takes |
|---|---|---|---|---|
| 1 | **Better running order, same dogs** (Hopefuls, Zephyr, XXL, Maximini) | **+27 (20–33)** | +3.0 pp | Nothing: **do it at the next competition** |
| 2 | **Saturdays as clean as Sundays** | **+28 (17–42)** | +3.1 pp | Find out what differs; the cause is unknown |
| 3 | **Close each team's fault gap to its division peers** | **+26 (21–33)** | +2.9 pp | Targeted start, pass and run training |
| 4 | Bring a bench dog (Pax) into one team | +3 to +45 | – | Pax's availability; optimistic |
| 5 | Keep full speed on hot days | ≤ +3.5 (1.8–5.4) | ≤ +0.4 pp | Welfare first; little to win |
| – | Lane colour, partner's sex or neuter status | 0 | – | No effect found: no action needed |
| – | *For scale:* no own faults at all | +148 (127–165) | +16.4 pp | *Ceiling, not a target* |

Levers 1–3 overlap in part (e.g. the Hopefuls reorder removes false starts), so they don't simply add up. Fully realised and added up they would come to about +9 pp; since they overlap and won't all be achieved at once, **about +5 pp of win rate in 2024** is a reasonable planning target. This is a judgement, not a model output.

**The coach's questions in one line each:**
- **Q1 – Lane colour:** no effect that matters (±0.006 s per run). No lane strategy is needed.
- **Q2 – Passing onto intact/neutered male/female:** no measurable effect on racing performance. One lead to check: passes onto young intact males are held back more often.
- **Q3 – Per competition:** all tables are in `reports/phase4a/`. WRFT fell behind its peers on 4 of 20 days, always through faults, never through speed.
- **Weather:** heat above 20 °C slows *every* dog by +0.08 s per run per 10 °C. Humidity, wind and rain don't matter. Of the four suspected factors, only heat (above 20 °C) is confirmed.
- **Ideal line-up:** A-team **Maggie > Enola > Pax > Alfie** (19.3 s expected per heat). The robust core is Enola, Alfie and Maggie.

---

## Findings, ranked by business impact

Each finding gives the claim, the evidence, the impact in extra wins, our confidence, the **action for the coach**, and how to check it next season.

**Confidence levels**
- **High:** a strong effect, robust to the sensitivity checks.
- **Medium:** a solid effect, but its size or cause is uncertain.
- **Lead:** worth checking, but not proven.

### F1 · Faults, not speed, decide WRFT's heats
- **Claim:** WRFT is as fast as the field but faults more, especially false starts. Faults are the single biggest reason WRFT loses.
- **Evidence:**
  - median run 4.28 s (WRFT) vs 4.27 s (field);
  - win rate 40.8 % (CI 37.9–43.7) vs 45.6 %; clean heats 54.4 % vs 56.6 %;
  - **heats with a false start: 15.8 % vs 10.6 %** [2.5];
  - a clean team beats a faulting opponent 85.0 % of the time, and wins only 8.9 % when it faults against a clean opponent [2.3];
  - fault status explains the heat result much better than speed (McFadden pseudo-R² 0.25 vs 0.017) [2.3];
  - a corrected fault costs about 7.8–8.3 s of rerun, more than any speed difference between teams [2.4];
  - WRFT lost 660 heats; 62.1 % included its own fault, and **155 (23.5 %) were avoidable**: lost on a fault although WRFT was typically faster that day [2.4].
- **Impact:** removing every own fault would add +148 wins (CI 127–165), +16.4 pp. This is the ceiling, and it shows the size of the prize.
- **Confidence:** high. The definition of a good result (a won heat) and the model are in [2.3].
- **Action:** make **clean heats the team's main KPI**, ahead of times. F2–F4 say which faults to fix first and how.
- **Check next season:** clean-heat rate per team and competition day (field 2023: 56.6 %).

### F2 · Saturdays are much less clean than Sundays
- **Claim:** at two-day events the same WRFT teams run far more cleanly on day 2. Their speed doesn't change; their faults drop.
- **Evidence:**
  - same team, same event, controlled for weather, hurdle and the heat number of the day [5.3]:
    - clean-heat rate on day 2 **+16.0 pp** (CI 9.5–22.5); field +18.9 pp (15.9–21.9);
    - false starts −10.0 pp per start (−13.4 to −6.7);
    - run time unchanged (field +0.000 s per run);
  - at heat level (`impact_day2_faults.csv`): false-start heats −11.6 pp, early-pass heats −8.2 pp, run faults no change [6.2].
- **Impact:** if day 1 were as clean as day 2, **+28 wins (CI 17–42), +3.1 pp**.
- **Confidence:**
  - the effect is **high** confidence: large, and found in WRFT and the field alike, both per start or pass and per heat [5.3, 6.2];
  - its **cause is unknown**. Nerves, a new ground, travel, the warm-up and Saturday's race format are all possible, so this lever is to investigate before it can be pulled.
- **Action:**
  - ask the handlers what differs on Saturdays (arrival time, warm-up, ring walk, practice slots, crate time);
  - **at the next two-day events, give Saturday the Sunday routine** (e.g. a full familiarisation and box practice in the practice slot);
  - log the routine on both days.
- **Check next season:** the day-1 vs day-2 clean-heat rate per event. The target is a gap under 5 pp.

### F3 · The running order of four teams can be improved at no cost
- **Claim:** four teams lose seconds and heats through their running order alone, with the same four dogs.
- **Evidence:** expected heat time from the dog profiles; the exhaustive search scored 2.7 M line-ups [5.8–5.9].

  | Team | Now | Recommended | Expected s/heat saved | Extra wins per season (CI) |
  |---|---|---|---|---|
  | Hopefuls | Cookies > Enola > Maggie > Tyna | **Maggie** > Tyna > Cookies > Enola | 2.25 | **+12.1 (8.9–14.5)** |
  | Zephyr | Rex > Rocky > Scotty > Gordon | **Rocky** > Rex > Gordon > Scotty | 1.35 | +8.5 (6.5–9.9) |
  | XXL | Rex > Hank > Gerry > Bailey | **Gerry** > Bailey > Rex > Hank | 1.03 | +4.0 (2.6–5.0) |
  | Maximini | Nina > Brooke > Bree > Alex | **Bree** > Brooke > Alex > Nina | 0.36 | +2.5 (1.6–3.3) |
  | Dreamers, Nightfall, Wonders | – | already (near) optimal | ≤ 0.11 | ≈ 0 |

  - Most of the gain comes from **who starts**:
    - Cookies false-starts **37.3 %** of 51 starts (CI 25.3–51.0);
    - Rex false-starts 23.6 %;
    - in starts, speed and safety go together: dogs with a median start of 0.05–0.08 s false-start least (8.3 %), and slow starters (0.14–0.18 s) most (15.7 %) [2.6].
- **Impact:** **+27 wins (CI 20–33), +3.0 pp** for the four teams together.
- **Confidence:** medium-high.
  - The speed profiles rank line-ups well (back-test Spearman 0.91 on Sep–Oct heats) [5.10].
  - The fault part is a tilt, not a forecast (AUC 0.55): it works because it moves the starts to dogs with *proven* low false-start rates.
  - The Hopefuls recommendation opens with Maggie, who has only 14 starts (0 false starts). Enola, with 156 starts, is the proven alternative.
- **Action:**
  - **use the recommended orders from the next competition**;
  - only dogs with a proven start record open a heat;
  - trial Maggie as a starter in practice.
- **Check next season:** the false-start heat rate per team (target: at or below the field's 10.6 %).

### F4 · Each team has one or two specific fault habits to train away
- **Claim:** the fault gaps to the division peers are concentrated in a few team × fault combinations, and often in a few dogs.
- **Evidence** (team minus division peers, Holm-corrected [2.5]; dog rates from the scorecards [2.7]):

  | Team | Gap to peers | Main dogs (2023, all teams) | Extra wins if closed (CI) |
  |---|---|---|---|
  | XXL | **false starts +20.0 pp** (15.1–24.9) | Scotty 44.4 % of 27 starts, Negro 38.5 %, Rex 23.6 % | +3.6 (2.4–4.9) |
  | Zephyr | **run faults +7.9 pp** (6.2–9.6) | Ted 32.3 % of 31 runs | +4.4 (2.9–5.7) |
  | Hopefuls | **early passes +5.8 pp** (2.3–9.3) | Moon 16.7 % of 120 passes, Maggie 11.7 % | +3.0 (1.1–5.0) |
  | Maximini | early passes +4.2 pp (n.s. after Holm) | Bree 13.4 %, Bella 10.8 % | +2.8 (0.9–4.9) |
  | Nightfall, Dreamers, Zephyr, Hopefuls | false starts +3.0 to +5.5 pp | Sunny 17.0 % (Dreamers) | +1.2 to +2.1 each |

  - **By fault type, all teams together:** false starts +11.5 wins (7.7–15.6), early passes +7.9 (4.7–11.9), run faults +6.2 (4.0–8.4); every gap at once **+26 wins (21–33)**.
  - **Passes: don't chase tighter passes.**
    - The early-pass rate is 10.9 % for dogs passing at ≤ 0.08 s, 5.7 % at 0.25–0.35 s and 3.4 % above 0.35 s [2.6];
    - the expected cost (time plus fault risk) is lowest at 0.25–0.35 s and nearly flat from 0.12 to 0.35 s (`pass_window.csv`);
    - WRFT's median pass is 0.20 s (field 0.15 s), already inside the safe window.
- **Impact:** +26 wins (CI 21–33), +2.9 pp, overlapping with F3 (a better starter is also a false-start fix).
- **Confidence:**
  - medium-high for XXL, Zephyr and Hopefuls (significant after Holm);
  - the smaller gaps are within noise.
- **Action:**
  - **start training** for Scotty, Negro and Rex (XXL/Zephyr);
  - **run-fault work** (box turn, ball retrieval) for Ted before he races again;
  - **pass training** for Moon, Bree and Maggie: aim for a **0.12–0.35 s** pass rather than an ever tighter one.
- **Check next season:** the per-dog fault rates on the scorecards (`reports/dog_scorecards.csv`), refreshed after each competition.

### F5 · Line-up composition: a strong core, one open question (Pax), and no height dog
- **Claim:** WRFT's best four dogs, in the best order, would be a top team. The core is stable; the fourth dog is not.
- **Evidence:**
  - **A-team: Maggie > Enola > Pax > Alfie**, 25 cm hurdle: 19.28 s expected per heat, 16.60 s without faults, P(clean heat) 0.70 [5.8];
  - in 50 resamples of the season, Enola is in the best line-up 100 % of the time, Alfie 72 %, Pax 58 % and Maggie 56 % [5.10];
  - **bench swaps:** Pax is the best bench dog for every team (+15.9 wins for Hopefuls, CI 12.2–18.6), but he can join only one team, and he last raced in July;
  - **height dog:** no small WRFT dog pays off in a top team. The lower hurdle saves the partners less than the small dog loses: Easy −0.55 s and Gordon −2.43 s per heat net [5.9];
  - for Zephyr, replacing Gordon (15 cm) with Pax would add up to +45 wins, but a team that much faster would be seeded into a faster division, so this is optimistic.
- **Impact:** +3 to +45 wins, depending on the team and on Pax. These rows are not additive.
- **Confidence:** medium. The speed ranking is reliable (Spearman 0.91); the exact fourth dog changes with the data.
- **Action:**
  - confirm **Pax's availability** for 2024;
  - build the top team around **Enola, Alfie and Maggie**, plus the best available of Pax, Tyna and Alex;
  - don't select a dog *only* to lower the hurdle.
- **Check next season:** the top team's clean time against the predicted 15.95 s of runs (back-test MAE 0.34 s).

### F6 · Heat slows everyone; it is a welfare issue more than a results lever
- **Claim:**
  - above about 20 °C, every dog runs slower;
  - below 20 °C temperature doesn't matter;
  - humidity, wind and rain don't matter for speed.
- **Evidence** (same dog, same event; field) [5.2]:
  - **+0.083 s per run per 10 °C above 20 °C** (CI 0.050–0.117, +1.95 %), about 0.3 s per heat on a 30 °C day;
  - WRFT dogs show the same direction (+0.072 s, CI −0.006 to +0.152: too few dogs to be conclusive on their own);
  - humidity +0.018 s per +20 pp, wind −0.007 s per +3 m/s and rain −0.006 s: all real but negligible or equivalent to zero;
  - weather plus the season explain 77 % of the differences between competition days [5.5];
  - fatigue: each earlier run that day adds +0.005 s [5.3].
- **Impact:** heat slows the opponents too, so even if WRFT kept its full speed on every hot day, the gain would be **at most +3.5 wins** (CI 1.8–5.4).
- **Confidence:** high for heat above 20 °C (robust in 20 sensitivity variants [5.4]); faults vs weather is inconclusive.
- **Action:** a **hot-day protocol above about 22 °C**: shade, cooling and water between heats, a short warm-up, and fewer runs per dog where the squad allows. Do it for the dogs' welfare; expect little effect on results.
- **Check next season:** the dog-adjusted speed index per day against the forecast temperature.

### F7 · Q1 – Lane colour has no effect that matters
- **Evidence:**
  - the same dog, blue vs red: +0.006 s per run (CI 0.003–0.010) in the field and +0.006 s (−0.006 to +0.018) in WRFT; both are within the ±0.05 s equivalence margin [4.2];
  - the largest venue asymmetry among 28 ring-days is 0.032 s per run;
  - starts, passes and fault rates are equivalent too;
  - lanes are drawn once per race (the first team listed is always blue) [4.1].
- **Confidence:** high for speed. WRFT's own win and fault rates are inconclusive (too few races), but nothing points to a lane effect.
- **Action:** none; no lane strategy is needed.

### F8 · Q2 – The partner's sex or neuter status doesn't change performance
- **Evidence:**
  - 3,260 WRFT passes;
  - no joint test is significant after Holm, for racing pass time, `ok` share, early passes or the outgoing dog's run time [4.3];
  - age is a confound: intact dogs are much younger;
  - **lead:** passes onto intact males are held back (> 1 s) more often, +10.6 pp (CI 3.1–18.1; Holm p = 0.21).
- **Confidence:**
  - "no evidence of an effect", not proof of absence: there are only 2 intact females and 8 intact males;
  - the held-pass result is a lead.
- **Action:** choose pass partners by speed and reliability, not by sex. Ask the handlers whether holding back passes onto young intact males is deliberate.

### F9 · Q3 – Per competition: bad days were fault days
- **Evidence** (20 WRFT competition days, `competition_days.csv`) [4.4]:
  - WRFT's win rate was below its peers on 4 days after Holm: Eager's Cup Sun −19 pp, Flyvaryors Sat −21 pp, EFC Sun −39 pp, Czech championship Sun −23 pp;
  - its **clean time never differed** from the peers;
  - avoidable losses peaked at Budějckej Sunday (69 %), WRFT's fastest day;
  - the same dogs ran between −2.0 % and +1.9 % of their season average from day to day, with the hot days slowest;
  - the same dogs also got faster through the season (−0.29 % per month, CI −0.36 to −0.22).
- **Confidence:** descriptive. The causes are tested in F2 and F6.
- **Action:** after each competition, review the **per-day table** (clean-heat rate, faults by type, avoidable losses) rather than the times.

---

## Action plan

| # | Action | Who | When | KPI | 2023 → target |
|---|---|---|---|---|---|
| 1 | Run the recommended orders (Hopefuls, Zephyr, XXL, Maximini) | Coach | Next competition | False-start heats per team | 15.8 % (club) → ≤ 10.6 % |
| 2 | Only dogs with a proven start record open; trial Maggie as a starter in practice | Coach, handlers | Now | Starter's false-start rate | Cookies 37 % → ≤ 10 % |
| 3 | Give Saturday the Sunday routine; log both days | Coach | Next two-day event | Day-1 vs day-2 clean-heat gap | 16 pp → < 5 pp |
| 4 | Start training: Scotty, Negro, Rex | Handlers | Off-season | XXL false-start gap to peers | +20 pp → 0 |
| 5 | Run-fault work: Ted before racing again | Handler | Off-season | Ted's run-fault rate | 32 % → < 5 % |
| 6 | Pass training aimed at 0.12–0.35 s: Moon, Bree, Maggie | Handlers | Off-season | Early-pass rate per pass | 12–17 % → ≤ 8.8 % (field) |
| 7 | Hot-day protocol above ~22 °C | Coach | Summer events | Dog welfare; speed index on hot days | – |
| 8 | Decide on Pax; build the top team around Enola, Alfie, Maggie | Coach | Before the 2024 season | Top team's clean time | ~16 s of runs |
| 9 | Keep the data flowing: same sheets, plus Saturday routine, held passes (deliberate?), indoor/outdoor | Coach | Every competition | Scorecards refreshed | – |

## Open questions for the coach
1. **Is Pax available in 2024?** He last raced in July and is in the A-team.
2. **What is different on Saturdays?** Arrival, warm-up, practice slots, race format?
3. **Can Maggie start?** She has only 14 starts so far, all clean.
4. **Are passes onto young intact males held back on purpose?**
5. **Were any events indoors?** All were assumed outdoor for the weather.

## Limitations
- **Observational data.** The ledger's what-ifs come from models of what happened (association, not proven cause). They rank the levers well; the exact numbers are not promises.
- **Small numbers for WRFT.** There are 7 teams and 50 dogs, so many WRFT-only tests are inconclusive. Where possible, effects were estimated on the whole field (903 dogs) and checked on WRFT.
- **Opponents stay as observed.** A team that becomes much faster would be seeded higher and meet faster opponents, so large line-up gains are optimistic.
- **Weather is from a reanalysis grid** (Open-Meteo, ~10 km), not on-site measurement. Rain is used as dry/wet only [3.4].
- **The fault model is weak at the dog level** (AUC 0.55), so it can't predict which heat will fault; it only tilts the line-up search towards reliable dogs.
- **Thin groups:** intact females are 2 dogs, intact males 8.

## Sources
- **Impact ledger:** `reports/phase5/impact_ledger.csv` (39 levers, with CIs and basis).
- **All quoted numbers:** `reports/phase5/key_numbers.json`.
- **Walk-through:** `notebooks/05_synthesis.ipynb`.
- **Underlying analyses:** `reports/phase3/`, `reports/phase4a/`, `reports/phase4b/` and `reports/dog_scorecards.csv`; methods in `ANALYSIS_LOG.md` Steps 2–6.
