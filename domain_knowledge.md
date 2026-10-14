# Flyball Domain Knowledge for the WRFT 2023 Analysis

This file collects everything from the reference sources in `flyball_elemzes.md` (section *Domain Tudás*) that is relevant to the project. Two of those links turned out to be broken, so supplementary official sources are used as well, each clearly marked. The last section translates the domain rules into concrete consequences for the data cleaning and analysis.

Compiled: 2026-10-13

---

## 0. Sources and their status

| # | Source (as given in the brief) | Status | What was used |
|---|---|---|---|
| 1 | YouTube – *Flyball Semi-Finals & Final Part 3, Crufts 2023* (`watch?v=FDUHV3LjISY`) | Video page available; 4 min 48 s; published by Crufts on 12 Mar 2023. The video itself cannot be watched from this environment, and automatic subtitles were blocked (HTTP 429). | Title, description and the official Kennel Club press release about the same final ([royalkennelclub.com](https://www.royalkennelclub.com/media-centre/2023/march/belgium-stars-break-crufts-flyball-record-again)) |
| 2 | Wikipedia – *Flyball* (EN) | Available | Full article |
| 3 | Hungarian Flyball rulebook (`dogland.hu/.../flyball-szabalyzat.pdf`) | **Broken**: the site returns 403/404. The Wayback Machine snapshot (2024-05-29) only returns the site's robots.txt. | Not available. Replaced by **3a** below, the international FCI rulebook. National FCI-member rulebooks, the Hungarian one included, are based on it. |
| 4 | UKFL Hungary, chapter 9 (`UKFL-Svab-Ford-1-o.pdf`) | The link has a typo: it ends in `1-o` (letter o) instead of `1-0` (zero). The corrected URL works. | Full UKFL rulebook v2.1, Hungarian translation 1.0 (83 pages). Used: ch. 9 (measurement, hurdles, team changes, health), ch. 8 (race rules), ch. 7.3–7.4 (divisions, formats), ch. 10 (course, timing system). |
| 3a | *Supplementary:* **FCI Regulations for Flyball Competitions** (annex of FCI circular 1/2023, last amended Nov 2022) – [oekv.at PDF](https://www.oekv.at/media/upload/editor/files/%C3%96KV/FCI%20Zirkulare/1-2023-annex-en.pdf) | Available | Full text. **This is the rulebook that matches our data**: metric hurdle heights of 15–32.5 cm in 2.5 cm steps, plus the ulna table (see §4). |
| 3b | *Supplementary:* FCI Judges' Guidelines for the Ulna Measuring Method (2017), hosted by ČMKU, the Czech kennel club – [cmku.cz PDF](https://www.cmku.cz/data/dokumenty/1653-5516-prirucka-k-mereni-flyball.pdf) | Available | Measurement procedure |

> **Why FCI matters most for us:** 10 of the 11 competitions are Czech (FLYBALLCZ, run under the FCI-member ČMKU), and the EFC is a European championship. The UKFL rulebook uses **inch-based** heights (6"–12" = 15.24–30.48 cm), which do **not** match our data (15, 17.5, … 32.5 cm). The FCI table does match, so for anything numeric (heights, ulna bands, break-out rules) FCI takes precedence. UKFL is still a good source for general mechanics, which are almost identical.

---

## 1. The sport in one paragraph

Flyball is a **relay race between two teams of four dogs**, running side by side in two parallel lanes. Each dog jumps **4 hurdles**, presses the spring-loaded pad of the **flyball box**, catches the released tennis ball, and returns over the same 4 hurdles across the start/finish line, carrying the ball. The next dog may cross the line only after the returning dog has reached it (the **pass** or **changeover**). Ideal running is "nose-to-nose" at the start line. The first team whose four dogs have all completed the course **without uncorrected faults** wins the heat. *(Wikipedia; FCI §1.02; UKFL 8.1)*

Breeds: herding dogs dominate, especially Border Collies, and mixed breeds are very common. Small dogs are valued as **"height dogs"** because the hurdle height of the whole team is set by its smallest dog. Their main limitation is triggering the box pad. *(Wikipedia)*

---

## 2. Terminology and how it maps to the dataset

| Concept | Definition (FCI §1.03) | Czech column / value | EFC column / value | Hungarian |
|---|---|---|---|---|
| Competition | An event (usually a 2-day weekend) | sheet title row | sheet title row | verseny |
| Ring | One racing area with 2 lanes; big events run several rings in parallel | "1. ring" / "2. ring" in title | "Ring 1/2" | ring |
| Division | Group of teams with similar seeded speed | `Divize` | `Division` | divízió |
| Race | Two teams meet; consists of several heats (typically 3–5) | consecutive rows with the same team pair | same | mérkőzés |
| **Heat** | One session from start to the judge's whistle; a re-run heat still counts as one heat | **a pair of rows** (one row per team) with the same `kdy` time | same, `when` | futam |
| Lane | One of two parallel courses; the two hurdle sets **must have different colours, preferably red and blue** (FCI §4.01a) | **font colour of the team-name cell (red/blue)** | same (palette idx 11 = red, 15 = blue) | sáv / pálya |
| Team total time | Green light → last dog crossing the line, including reruns | `celkem` | `total time` | összidő |
| Outcome | Win / loss / tie | `V`/`P`/`R` | `W`/`L`/`T` (sheet 2 uses Czech `V`/`P`) | győzelem / vereség / döntetlen |
| Hurdle height | Set by smallest dog in the heat | `překážky` | `Hurdles` | akadálymagasság |
| Start time | First dog's crossing time relative to the green light | `start` | `start` | rajtidő |
| Changeover (pass) | Gap between returning dog and next dog at the line | `stříd.` | `chng` | váltási idő |
| Dog run time | Line-to-line time of one dog | `1.pes`…`4.pes` | `1.dog`…`4.dog` | futási idő |
| Fault codes | — | `mimo` (outside / missed hurdle), `vběhl` (ran in), `chyba` (pass error, unquantified), `ok/OK/Ok` (≈0.00 pass) | `outside`, `run in`, `error`, `ok` | hibák |
| Break-out (BO) | Running faster than the division's allowed limit | — (not recorded) | — | break out |
| Clean time (CT) | Net time of the 4 dogs, **excluding start and crossing times**, in a heat without mistakes (FCI §1.03h) | derivable: sum of 4 run times | derivable | tiszta idő |

---

## 3. Course and timing (the physics behind our columns)

### 3.1 Course geometry *(FCI §1.05, UKFL 10.1)*
- Start line → 1st hurdle **1.83 m**, between hurdles **3.05 m**, last hurdle → box **4.57 m**, so start line → box = **15.55 m**.
  - One dog run is therefore about **31.1 m**. A 4.0 s run is about 7.8 m/s (≈ 28 km/h) on average, including the box turn.
- Lane centre-lines are 5 m apart (FCI, ±1 m). Both lanes must be **identical in length and parallel** (FCI). UKFL 10.1.15 requires the lanes to be "as identical as possible, so racing happens under the same conditions on both". **Under the rules, lane colour should therefore have no effect.** A measured effect would point to environmental asymmetry (sun, wind, slope, spectators, surface wear) or dog perception, not the rules. This is the hypothesis for **Question 1**.
- Surface: grass, sand or mats (FCI). For outdoor events, UKFL requires any slope to rise *towards* the box. The EFC is an outdoor competition (Wikipedia).

### 3.2 Electronic Judging System, EJS *(FCI Annex 4, UKFL 10.6, Wikipedia)*
- Light tree: 3 yellow lights (or 1 red + 2 yellow) at **1.0 s intervals**, then green. **The green light starts the timer.**
- Breaking the beam **before green = false start**, which explains the **negative start times** in the data. The start value is the first dog's line crossing relative to green; ideally a small positive number.
- Two sensor columns: the *line beam* on the start/finish line and the *passing beam* 152 mm towards the first hurdle. Breaking the line beam while it is not "safe" means a **pass fault (early pass)**. This explains the **negative changeover times** and the `chyba`/`error` values: the machine detected an early pass but could not quantify it.
- Precision: timed to **0.001 s**, displayed to **0.01 s** (with rounding), accuracy ±3 ms, lane-to-lane difference ≤ 2 ms. This explains values like `-0.008` and `0.006`. Differences below about 0.01 s are within measurement precision.
- A **tie** is shown when both lanes have identical times, which explains the rare `R`/`T` outcomes.
- The EJS display updates an elapsed time **each time the line beam is broken**. The individual dog and pass times are derived from these line crossings.

### 3.3 Total time structure *(derived from the rules and verified on our data)*
For a heat without reruns:

```
total = start + run1 + chg2 + run2 + chg3 + run3 + chg4 + run4
```

**Verified on the dataset:** of the 6,286 rows where all 9 components are numeric (`ok` = 0), **87.7 %** satisfy this identity within ±0.02 s (rounding). The remaining rows are larger, by up to about 54 s, because **rerun time of faulted dogs is added** to the total but has no column of its own.

---

## 4. Hurdle heights and dog measurement *(FCI §1.06, §1.11, §4.01; UKFL ch. 9)*

### 4.1 FCI ulna table (the scale our data uses)
The ulna (forearm) is measured from the elbow to the pisiform (accessory carpal) bone, with the foot at 90°. **A value exactly on a limit gets the lower height** (e.g. 12.50 → 20.0 cm, 12.6 → 22.5 cm).

| Ulna length | Jump height |
|---|---|
| ≤ 10.00 cm | 15.0 cm |
| 10.00 – 11.25 cm | 17.5 cm |
| 11.25 – 12.50 cm | 20.0 cm |
| 12.50 – 13.75 cm | 22.5 cm |
| 13.75 – 15.00 cm | 25.0 cm |
| 15.00 – 16.25 cm | 27.5 cm |
| 16.25 – 17.50 cm | 30.0 cm |
| > 17.50 cm | 32.5 cm |

- Hurdles adjust in **2.5 cm steps, 15.0–32.5 cm**. A dog that cannot be measured jumps the maximum, 32.5 cm.
- Measurement procedure *(FCI guidelines, 3b)*: a dog wanting less than the maximum is measured by **2 judges, one paw each**. If they disagree, the **shorter** value counts, or a third judge decides.
- **The team's hurdle height = the jump height of the smallest dog actually running in that heat** (FCI §1.11a; UKFL 9.2.4). Each team sets its own hurdles (FCI §1.11c).
- Running at a hurdle height below what is allowed loses the affected heats (UKFL 9.6).
- **UKFL** uses inches instead: 6"–12" (15.24–30.48 cm) in 1" steps, with its own ulna bands (UKFL 9.4). This **doesn't match** our data, which confirms the data follows FCI rules.
- The brief notes that the Hungarian rulebook's measurement section is outdated. This is consistent with the FCI metric table being the current standard.

### 4.2 Check of our master data against the FCI table
- The **4 suspicious ulna values** become consistent once the obvious entry errors are corrected:
  - Speedy 1.491 → 14.91 → 25 ✔
  - Henry 1.209 → 12.09 → 20 ✔
  - Bruno 175.5 → 17.55 → 32.5 ✔
  - Falco 152.8 → 15.28 → 27.5 ✔
  - So these are decimal-point or unit errors, not unknown values.
- **49 of 51 dogs** match the FCI table exactly. The 2 mismatches sit right on a band edge, within measurement precision:
  - Punk: ulna 10.02, recorded 15 cm, table 17.5 (limit 10.00).
  - Hank: ulna 16.28, recorded 27.5 cm, table 30 (limit 16.25).
  - Likely explanation: the official height came from the shorter of two measurements (FCI guideline), while the master sheet holds a different reading. **The recorded jump height should be treated as authoritative.**

---

## 5. Race rules that shape the data *(FCI Art. II, UKFL 8.11)*

### 5.1 Start
- The first dog may not cross before the timer starts. A **false start is a fault: the first dog must re-run after the four initial dogs** (FCI §2.05c).
- UKFL differs slightly: the first false start restarts the heat, the second counts as a fault (UKFL 8.11.A).
- Dogs may start from standing or running (UKFL). A **running start** is what produces the very small positive start times (≈0.0–0.2 s) of good teams.
- **Practice start** (FCI §2.05d): only in a team's **first two races** of the tournament, **one dog per team** may run a practice start before the first heat.
  - → *Hypothesis for cleaning:* the rows with only **one dog, a ~4–5 s total and no outcome** (e.g. the first rows of Eager's Cup, Máchale and Budějckej) are **practice starts, not real heats**.

### 5.2 Passes / changeovers
- The next dog may cross the start line only after the previous dog has crossed it (FCI §2.05e). An **early pass is a fault**, and that dog must re-run.
- UKFL 8.15.2 says it is unsportsmanlike to **deliberately hold dogs back** at starts or passes to manipulate times. This is linked to the break-out rule (§6).

### 5.3 Faults and reruns
- Faults: false start, early pass, **missed hurdle** (`mimo`/outside), **returning without the ball / dropped ball**, not triggering the box, handler or object crossing the line, box-loader faults (FCI §2.03d, §2.04; UKFL 8.11.D).
- `vběhl`/`run in` (ran in) likely means the dog ran around or behind the box instead of using it correctly, or crossed into the lane improperly, as the dataset docs describe ("befutott a gép mögé"). Either way it is a box/course fault that requires a rerun.
- Faulted dogs **re-run after the four initial dogs, in the order the faults happened** (FCI §2.05f). A run is either clean or faulted: faults don't accumulate within one run (UKFL 8.11.C.5).
- **Fixing a fault is optional, but a heat with an uncorrected fault is not valid**: "No Time" (NT), and the opponent wins (UKFL 8.11.F.5).
  - **Verified on our data:** of 510 rows with a negative start and **no extra rerun time** in the total, **494 (97 %) are losses**. Of 157 negative-start rows **with** rerun time, 45 % are still wins. Correcting a fault costs about a full dog run (≈4–5 s) but keeps the heat alive.
- A **knocked-down hurdle is not a fault** for the dog (UKFL 8.11.I), but dogs must still clear it as if it were standing (FCI §2.05i).
- **Interference** with the other lane loses the heat (FCI §2.05b; UKFL 8.11.H).
- If a dog soils the ring, that heat (or the next one) is lost (FCI §2.05h).

### 5.4 Heat result
- The team that completes the course first, with all faults corrected, wins.
- Both teams can lose a heat ("loss/loss"), for example if neither corrects its faults or both break out (UKFL 8.11.M).

---

## 6. Competition structure *(FCI Art. III, §1.08–1.10, §2.05j; UKFL 7.3–7.4)*

- **Seeding into divisions:** at registration each team submits a **reference time**, and the organiser groups similar teams into divisions so racing is close. A UKFL division has 3–7 teams. Division 1 is the fastest.
- **Break-out rule (FCI §2.05j):**
  - **BO time = fastest seeded time of the division − 0.5 s** (if that time is ≤ 20 s) or **− 1.0 s** (if > 20 s).
  - **The fastest division has no break-out.**
  - Running faster than BO means **that heat is automatically lost**. Three break-outs in one competition mean all later heats are lost.
  - **Consequence for analysis:** in lower divisions, teams have an incentive **not** to run as fast as they can. Their best times may be capped just above the BO limit, so "speed" in lower divisions is partly a strategic choice. When comparing teams, analyse **within division** or in Division 1, which has no limit.
- **Formats:**
  - **Round Robin**: each team races every other team in its division; 2 points for a win, 1 for a tie, 0 for a loss; ties broken by the fastest time.
  - **Speed Trial**: ranking by fastest time.
  - **Single or double elimination.**
  - Races have a fixed number of heats (3, 4 or 5) or are best-of-3 / best-of-5.
- **Team composition:** up to **6 dogs registered, 4 running per race**. The line-up must be given before the first heat; **substitutions between heats are allowed** if declared (FCI §1.10).
  - → Line-ups can change heat by heat. That matches our data: 40 of the 50 WRFT dogs ran in more than one WRFT team.
- UKFL 8.7.4: **a dog may appear on only one team sheet per day.** UKFL 8.8.3: a dog may not run in two regular teams at the same competition. *(FCI has no explicit equivalent; worth checking in the data.)*
- Competitions are usually **two-day weekend events** hosted by a local club (Wikipedia). This matches the "Sat–Sun" dates of our competitions.

---

## 7. Dog eligibility and welfare *(FCI §1.07, UKFL 9.9–9.11)*

- Minimum age: **18 months** (FCI); 15 months in UKFL. → *Check:* all WRFT dogs should be at least 18 months old on each competition date (birth dates are in the master data).
- Dogs must be chipped or tattooed; the chip may be checked (FCI). Our master data has chip numbers.
- **Bitches in heat are not allowed in or around the competition site** (FCI §1.07e; UKFL 9.10.1). Pregnant bitches and those within 8 weeks of whelping are also excluded (UKFL).
  - → **Relevant for Question 2 (intact vs neutered, male vs female):**
    - Intact bitches regularly miss competitions, so their sample is smaller and possibly biased. We only have 2 intact females.
    - Intact females never race while in heat, so a "female in heat distracts the male" effect **can't happen at competitions**. Any sex/neuter effect on the *pass* must come from other factors.
- Injured or lame dogs may not compete. After surgery, dogs must wait 14 days (21 days for body-cavity surgery) (UKFL 9.10).
- Kennel cough: excluded for 21 days after symptoms end (UKFL 9.11). This explains why individual dogs may be missing from some competitions.
- Equipment: fixed collar or harness only; prong, slip and electric collars are banned; protective leg wraps are allowed (FCI §4.04).

---

## 8. Weather – what the rules say

- UKFL 8.2: the event's head judge may **shorten, pause or suspend racing because of unsuitable weather: extreme heat, cold or rain**. The rulebook explicitly treats weather as a factor in dog safety and performance, which supports the coach's hypothesis that it is worth testing.
- Outdoor surfaces (grass/sand) change with rain: grip, mud and slipperiness. Mats are required only when the surface is not grass or sand (FCI §1.05d).
- The UKFL slope rule and the "identical lanes" rule imply that **wind direction relative to the lane direction** is a plausible physical factor. A headwind on the way out becomes a tailwind on the way back, so the net effect on a full run may be small; crosswind may affect the two lanes differently.
- **Not in the sources:** the venue's lane orientation (compass direction) and indoor/outdoor status per competition. Without them, wind can only be analysed as speed, not as head- or tailwind.
- **Venues found during Phase 4.0** (`ANALYSIS_LOG.md` Step 3.1). Heroltice is the "Happy Herolky" dog-sport ground near Tišnov. Louňovice is the village near Mukařov, in the Praha-východ district. Pláně is the airfield near Plzeň. Blšany is the football ground in the Louny district, on a **grass** pitch. Both Blšany events (May and the Czech championship) used this ground. The surface of the other venues is not documented.

---

## 9. Benchmarks for plausibility *(Wikipedia; Kennel Club)*

| Benchmark | Value |
|---|---|
| Fastest single dog ever recorded | **3.383 s** (USA, 2025); 3.40 s (UK, 2021) |
| FCI/world team record | **14.07 s**, Roadrunners (BE), 14 Apr 2024, outdoor FCI event, **27.5 cm** hurdles, line-up of 3 Malinois × Border Collie × Whippet mixes + 1 Whippet |
| EFC record | **15.31 s**, Roadrunners, EFC 2018 (outdoor) |
| Crufts record | **14.27 s**, Roadrunners Beep Beep, Crufts final, 12 Mar 2023. This is the subject of the YouTube video. |
| Polish record | 14.84 s |
| Fast EFC teams in our own data | ≈ 15.8–16.5 s (e.g. DumbleDogs S, Jokers All-in) |

**Implications for cleaning:**
- A **dog run below about 3.3 s** is physically implausible and indicates a data error. Our data contains e.g. 2.36 s (BCCCZ) and negative run times.
- A **team total below about 14 s** for a complete 4-dog heat is implausible.
- Very long totals (30–86 s) are not errors in themselves: they come from reruns or from a heat that got stuck (for example a dog refusing). But they are not representative of performance, so separate them from the "clean" analysis.

### About the YouTube video (Crufts 2023 final)
- **Content:** a 4:48 live replay, "Flyball Semi-Finals & Final Part 3" from day 4 of Crufts 2023 (NEC Birmingham).
- **Final:** 16 teams, from eight qualifiers held across 2022. **Roadrunners Beep Beep** (Belgium) won and set a **Crufts record of 14.27 s**, beating their own 14.71 s from 2022. It was the third or fourth time the record fell that weekend.
- **Team:** 6 dogs registered (4 run per heat).
- **Captain Toom Milissen** on what decides elite racing: *"one mistake or one little bit of bad luck and the competition is over"*. At the top level, **avoiding faults (consistency)** matters as much as raw speed.
- The video demonstrates nose-to-nose passes, running starts, box turns and reruns visually. Its *factual* content for this project is captured above.

---

## 10. Implications for this project (checklist)

**Data cleaning**
1. Lane colour = font colour of the team-name cell (red/blue). This corresponds to the red/blue hurdle sets (FCI §4.01a).
2. Treat `ok/OK/Ok` as a 0.00 s pass. Treat `chyba/error` as an unquantified **early pass fault**. Treat `mimo/outside` and `vběhl/run in` as **dog run faults**. Treat negative start values as false starts and negative pass values as early passes.
3. Each heat is a pair of rows with the same timestamp; consecutive heats of the same pair of teams form a race.
4. Single-dog rows with a ~4–5 s total and no outcome are very likely **practice starts**. Exclude them from performance metrics.
5. Use the identity `total = start + Σruns + Σchanges` to detect **heats with reruns** (residual > 0). Compute FCI **clean time** (Σ of the 4 run times) as the main team-speed metric, because it is not distorted by reruns or starts.
6. Plausibility bounds: dog run ≥ ~3.3 s; complete clean heat total ≥ ~14 s.
7. Correct the 4 ulna entry errors (confirmed by the FCI table). Keep the recorded jump height as authoritative.
8. Validate that `překážky`/`Hurdles` equals the minimum jump height of the 4 WRFT dogs in each heat. Deviations mean wrong data, a wrong line-up, or a rule violation.
9. Validate that dogs are at least 18 months old, and check how often a dog appears in two different WRFT teams on the same day.

**Analysis**
1. **Q1 (lane colour):** under the rules, lanes are identical, so the null hypothesis is "no effect". Test on dog run times with the dog as a random effect, and also check whether teams switch lanes between heats.
2. **Q2 (passing onto intact/neutered male/female):** the relevant quantity is the **changeover time** of the incoming dog and possibly its run time. Intact females have tiny samples and are absent when in heat, so report this with care.
3. **Division and break-out:** compare speed within a division, because times in lower divisions may be strategically capped.
4. **Fault cost:** an uncorrected fault ≈ a lost heat. A corrected fault costs ≈ one dog run (≈4–5 s). This links faults directly to the coach's results, which makes it high business value.
5. **Line-up optimisation:** the hurdle height is set by the smallest dog. Including a small "height dog" lowers the hurdles for all four dogs, but only pays off if that dog is itself fast and reliable. Combine each dog's speed, start/pass skill, fault rate and jump height to optimise the 4-dog line-up and running order. The order matters too: the start specialist runs first, and reliable passers go in the middle positions.
6. **Weather:** the rules recognise heat, cold and rain as risks. Test temperature, wind, humidity and precipitation against clean time and fault rates, at both dog and team level.
