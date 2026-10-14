"""Build the tidy tables from the raw sheets.

Pipeline (each step is one function, logged in ANALYSIS_LOG.md Step 1):

    read_all -> build_competitions -> parse_times -> pair_heats -> assign_races
             -> flag_heats -> build_runs -> flag_runs -> validate

Rows are never dropped: every exclusion is a boolean flag, so later phases
can filter, and test the effect of each rule (sensitivity checks).
"""

import re

import numpy as np
import pandas as pd

from flyball import config, dogs as dogs_mod, excel_reader, parse

SLOTS = parse.SLOT_SEQUENCE
RUN_SLOTS = ["run1", "run2", "run3", "run4"]
PASS_SLOTS = ["start", "chg2", "chg3", "chg4"]      # pass slot of positions 1-4
NUMERIC_CODES = {"number", "ok", "false_start", "early_pass"}


def slot_kind(slot: str) -> str:
    return "start" if slot == "start" else slot[:3]


def normalise_team(name: str) -> str:
    """Case- and whitespace-insensitive team key ('Jokers ALL-IN' == 'Jokers All-in')."""
    return re.sub(r"\s+", " ", str(name)).strip().casefold()


# --- 1. Competitions and raw rows -------------------------------------------------

def build_competitions(sheets) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach competition-day information to every raw row.

    Returns (rows, competitions) where competitions has one row per sheet x day.
    """
    frames, comps = [], []
    for sheet_no, (sheet, title, df) in enumerate(sheets, start=1):
        meta = parse.parse_title(title)
        dates = [pd.Timestamp(d) for d in config.DATE_OVERRIDES.get(sheet, meta["dates"])]
        df = df.copy()
        df["sheet_id"] = f"S{sheet_no:02d}"
        df["day_index"] = parse.assign_day_index(df["seconds_of_day"], len(dates))
        df["date"] = df["day_index"].map(dict(enumerate(dates)))
        df["comp_day_id"] = df["sheet_id"] + "-D" + (df["day_index"] + 1).astype(str)
        df["competition"] = meta["competition"]
        df["ring"] = meta["ring"]
        df["venue"] = meta["venue"]
        frames.append(df)

        overridden = sheet in config.DATE_OVERRIDES
        for day_index, d in enumerate(dates):
            day = df[df["day_index"] == day_index]
            comps.append({
                "comp_day_id": f"S{sheet_no:02d}-D{day_index + 1}",
                "sheet_id": f"S{sheet_no:02d}",
                "source": df["source"].iat[0],
                "sheet": sheet,
                "title": title,
                "competition": meta["competition"],
                "ring": meta["ring"],
                "venue": meta["venue"],
                "country": config.COUNTRY_BY_FILE[df["source"].iat[0]],
                "date": d.date(),
                "weekday": d.day_name(),
                "date_from_title": meta["dates"][day_index],
                "date_overridden": overridden,
                "day_index": day_index + 1,
                "n_rows": len(day),
                "n_wrft_rows": int(day["team"].str.startswith(config.WRFT_PREFIX).sum()),
                "divisions": ",".join(str(x) for x in sorted(day["division"].unique())),
                "first_heat": _clock(day["seconds_of_day"].min()),
                "last_heat": _clock(day["seconds_of_day"].max()),
            })
    rows = pd.concat(frames, ignore_index=True)
    rows.insert(0, "row_id", np.arange(len(rows)))
    rows["ring"] = rows["ring"].astype("Int64")
    competitions = pd.DataFrame(comps).astype({"ring": "Int64"})
    return rows, competitions


def _clock(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"


# --- 2. Time cells ----------------------------------------------------------------

def parse_times(rows: pd.DataFrame) -> pd.DataFrame:
    """Realign shifted rows, then turn every time cell into (seconds, code)."""
    rows = rows.copy()
    realigned = rows[SLOTS].apply(lambda r: parse.realign_shifted_row(r.to_dict()), axis=1)
    rows["row_realigned"] = realigned.map(lambda t: t[1] > 0)
    rows["overflow_value"] = realigned.map(lambda t: t[2]).astype("float64")

    cells = pd.DataFrame(realigned.map(lambda t: t[0]).tolist(), index=rows.index)
    for slot in SLOTS:
        parsed = cells[slot].map(lambda v, k=slot_kind(slot): parse.classify_time(v, k))
        rows[f"{slot}_raw"] = rows[slot]
        rows[slot] = parsed.map(lambda t: t[0]).astype("float64")
        rows[f"{slot}_code"] = parsed.map(lambda t: t[1])

    rows["total"] = rows["total"].astype("float64").round(config.ROUND_DP)
    rows["hurdle_cm"] = rows["hurdle_cm"].astype("float64")
    rows["outcome"] = rows["outcome"].map(config.OUTCOMES)
    return rows


# --- 3. Heats and races -------------------------------------------------------------

def pair_heats(rows: pd.DataFrame) -> pd.DataFrame:
    """Give each row a heat_id: two consecutive rows with the same clock time
    and swapped teams form one heat. A row with no matching partner is a heat
    of its own (`paired` = False)."""
    rows = rows.copy()
    nxt = rows.shift(-1)
    pairs_with_next = (
        (rows["sheet_id"] == nxt["sheet_id"])
        & (rows["seconds_of_day"] == nxt["seconds_of_day"])
        & (rows["team"] == nxt["opponent"])
        & (rows["opponent"] == nxt["team"])
    ).to_numpy()

    heat_ids, heat, i = np.empty(len(rows), dtype=int), 0, 0
    while i < len(rows):
        width = 2 if pairs_with_next[i] else 1
        heat_ids[i:i + width] = heat
        heat, i = heat + 1, i + width
    rows["heat_id"] = heat_ids
    rows["paired"] = rows.groupby("heat_id")["row_id"].transform("size").eq(2)
    rows["heat_time"] = rows["date"] + pd.to_timedelta(rows["seconds_of_day"].round(), unit="s")
    return rows


def assign_races(rows: pd.DataFrame) -> pd.DataFrame:
    """race_id: consecutive heats of the same two teams within a sheet-day.
    heat_in_race numbers the heats of a race, practice rows excluded."""
    rows = rows.copy()
    rows["team_norm"] = rows["team"].map(normalise_team)
    rows["opponent_norm"] = rows["opponent"].map(normalise_team)
    pair_key = rows["comp_day_id"] + "|" + rows[["team_norm", "opponent_norm"]].apply(
        lambda r: "|".join(sorted(r)), axis=1)
    key_by_heat = pair_key.groupby(rows["heat_id"]).first()   # heat_id = running order
    race_by_heat = (key_by_heat != key_by_heat.shift()).cumsum() - 1
    rows["race_id"] = rows["heat_id"].map(race_by_heat)

    real = rows.loc[~rows["is_practice"], ["race_id", "heat_id"]].drop_duplicates()
    real["heat_in_race"] = real.groupby("race_id").cumcount() + 1
    rows["heat_in_race"] = rows["heat_id"].map(real.set_index("heat_id")["heat_in_race"]).astype("Int64")
    return rows


# --- 4. Heat-level metrics and flags -----------------------------------------------

def flag_heats(rows: pd.DataFrame) -> pd.DataFrame:
    """Team-level metrics (clean time, rerun time, fault counts) and flags."""
    rows = rows.copy()
    codes = rows[[f"{s}_code" for s in SLOTS]].set_axis(SLOTS, axis=1)
    run_codes, pass_codes = codes[RUN_SLOTS], codes[PASS_SLOTS]

    rows["is_wrft"] = rows["team"].str.startswith(config.WRFT_PREFIX)
    rows["opponent_is_wrft"] = rows["opponent"].str.startswith(config.WRFT_PREFIX)
    rows["n_dogs"] = run_codes.ne("missing").sum(axis=1)
    rows["n_names"] = rows[config.NAME_COLUMNS].notna().sum(axis=1)

    rows["n_false_start"] = codes["start"].eq("false_start").astype(int)
    rows["n_pass_fault"] = codes[["chg2", "chg3", "chg4"]].isin(["early_pass", "error"]).sum(axis=1)
    rows["n_run_fault"] = run_codes.isin(parse.RUN_FAULT_CODES).sum(axis=1)
    rows["n_faults"] = rows[["n_false_start", "n_pass_fault", "n_run_fault"]].sum(axis=1)

    all_runs_clean = run_codes.eq("number").all(axis=1)
    rows["clean_time"] = rows[RUN_SLOTS].sum(axis=1).where(all_runs_clean).round(config.ROUND_DP)

    all_numeric = codes.isin(NUMERIC_CODES).all(axis=1)
    components = rows[SLOTS].sum(axis=1)
    rows["rerun_time"] = (rows["total"] - components).where(all_numeric).round(config.ROUND_DP)
    # Nullable booleans: NA where the row isn't fully numeric.
    rows["identity_holds"] = rows["rerun_time"].abs().le(config.IDENTITY_TOL).astype("boolean").where(all_numeric)
    rows["has_rerun"] = rows["rerun_time"].gt(config.IDENTITY_TOL).astype("boolean").where(all_numeric)

    rows["is_complete"] = rows["n_names"].eq(4) & codes.ne("missing").all(axis=1)
    rows["is_clean_heat"] = rows["is_complete"] & rows["n_faults"].eq(0)
    rows["is_zero_total"] = rows["total"].eq(0)
    rows["has_placeholder_dog0"] = rows[config.NAME_COLUMNS].isin([0, "0"]).any(axis=1)
    rows["no_outcome"] = rows["outcome"].isna()

    # Practice start (FCI 2.05d): one dog, no result, a single-run total.
    rows["is_practice"] = (
        rows["no_outcome"] & rows["n_dogs"].le(1) & rows["total"].le(config.PRACTICE_MAX_TOTAL)
    )

    # Red font should mark exactly the fault-like raw values (before realignment).
    # Empty cells are ignored: some are formatted red without any content.
    fault_like = {"false_start", "early_pass", "error", "outside", "run_in", "negative_run"}
    raw_fault = pd.DataFrame({
        s: rows[f"{s}_raw"].map(lambda v, k=slot_kind(s): parse.classify_time(v, k)[1] in fault_like)
        for s in SLOTS
    })
    red = rows[[f"red_{s}" for s in SLOTS]].set_axis(SLOTS, axis=1)
    filled = rows[[f"{s}_raw" for s in SLOTS]].set_axis(SLOTS, axis=1).notna()
    rows["red_font_mismatch"] = ((raw_fault != red) & filled).sum(axis=1)
    return rows


# --- 5. Runs (one row per dog slot) ---------------------------------------------

HEAT_CONTEXT = [
    "row_id", "heat_id", "race_id", "heat_in_race", "comp_day_id", "competition",
    "ring", "sheet", "excel_row", "date", "heat_time", "division", "team", "team_norm", "is_wrft",
    "opponent_norm", "lane", "outcome", "hurdle_cm", "is_practice", "no_outcome",
    "row_realigned",
]


def build_runs(heats: pd.DataFrame, dog_master: pd.DataFrame) -> pd.DataFrame:
    """Unpivot each heat row into its 4 dog slots and attach dog information.

    A slot is kept if it has a dog name or any run value. The dog key is the
    master-data name for WRFT rows (names are matched only inside WRFT rows,
    because opponents reuse names such as Abby or Chase), otherwise
    'team_norm|name', since nothing links dogs across opponent teams.
    """
    parts = []
    for pos in range(1, 5):
        pass_slot = PASS_SLOTS[pos - 1]
        part = heats[HEAT_CONTEXT].copy()
        part["position"] = pos
        part["dog_name_raw"] = heats[f"name{pos}"]
        part["run_time"] = heats[f"run{pos}"]
        part["run_code"] = heats[f"run{pos}_code"]
        part["pass_time"] = heats[pass_slot]
        part["pass_code"] = heats[f"{pass_slot}_code"]
        parts.append(part)
    runs = pd.concat(parts, ignore_index=True)
    runs = runs[runs["dog_name_raw"].notna() | runs["run_code"].ne("missing")]
    runs = runs.sort_values(["row_id", "position"]).reset_index(drop=True)

    name = runs["dog_name_raw"].map(lambda v: None if v is None or pd.isna(v) else str(v).strip())
    runs["is_placeholder_dog0"] = name.eq("0")
    name = name.where(~runs["is_placeholder_dog0"])
    runs["dog_name"] = name
    runs["dog_key"] = np.where(
        runs["is_wrft"], name, runs["team_norm"] + "|" + name.fillna("")
    )
    runs["dog_key"] = runs["dog_key"].where(name.notna())
    runs["is_wrft_dog"] = runs["is_wrft"] & name.notna()
    runs["wrft_name_unknown"] = runs["is_wrft_dog"] & ~name.isin(dog_master["dog"])

    runs["run_fault"] = runs["run_code"].isin(parse.RUN_FAULT_CODES)
    runs["pass_fault"] = runs["pass_code"].isin(parse.PASS_FAULT_CODES)

    by_row = runs.groupby("row_id")["dog_key"]
    runs["prev_dog_key"] = by_row.shift(1)
    runs["next_dog_key"] = by_row.shift(-1)

    attrs = dog_master.set_index("dog")[
        ["sex", "neutered", "category", "breed_group", "jump_height_cm", "birth_date"]]
    wrft_attr = attrs.reindex(runs["dog_key"].where(runs["is_wrft_dog"])).reset_index(drop=True)
    runs = pd.concat([runs, wrft_attr], axis=1)
    runs["age_months"] = dogs_mod.age_months(runs["birth_date"], runs["date"]).round(1)
    runs = runs.drop(columns="birth_date").astype({"neutered": "boolean"})
    for side in ("prev", "next"):
        key = runs[f"{side}_dog_key"].where(runs["is_wrft"])
        runs[f"{side}_category"] = key.map(attrs["category"])
    return runs


# --- 6. Run-level flags ------------------------------------------------------------

def flag_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Plausibility and outlier flags; `valid_speed` and `valid_pass` combine them."""
    runs = runs.copy()
    rt = runs["run_time"]
    is_number = runs["run_code"].eq("number")
    runs["run_too_fast"] = is_number & rt.lt(config.MIN_RUN)
    runs["run_over_ceiling"] = is_number & rt.gt(config.MAX_RUN)

    # Per-dog robust check: far slower than the dog's own typical run.
    base = is_number & ~runs["run_too_fast"] & ~runs["run_over_ceiling"] & ~runs["is_practice"]
    grp = rt.where(base).groupby(runs["dog_key"])
    med = grp.transform("median")
    mad = grp.transform(lambda s: (s - s.median()).abs().median()) * 1.4826
    n = grp.transform("count")
    threshold = np.maximum(config.DOG_OUTLIER_K * mad, config.DOG_OUTLIER_MIN_EXCESS)
    runs["run_dog_outlier"] = base & n.ge(config.DOG_OUTLIER_MIN_RUNS) & (rt - med).gt(threshold)

    runs["valid_speed"] = (
        is_number & ~runs["is_practice"] & ~runs["run_too_fast"]
        & ~runs["run_over_ceiling"] & ~runs["run_dog_outlier"]
    )

    pt = runs["pass_time"]
    pass_number = runs["pass_code"].isin({"number", "ok"})
    limit = np.where(runs["position"].eq(1), config.MAX_START, config.MAX_PASS)
    runs["pass_over_ceiling"] = pass_number & pt.gt(limit)
    runs["valid_pass"] = pass_number & ~runs["is_practice"] & ~runs["pass_over_ceiling"]

    reasons = {
        "practice": runs["is_practice"],
        "run_fault": runs["run_fault"],
        "run_missing": runs["run_code"].eq("missing"),
        "run_too_fast": runs["run_too_fast"],
        "run_over_ceiling": runs["run_over_ceiling"],
        "run_dog_outlier": runs["run_dog_outlier"],
    }
    runs["exclusion_reason"] = pd.DataFrame(reasons).apply(
        lambda r: ";".join(k for k, v in r.items() if v), axis=1).replace("", None)
    return runs


# --- 7. Validation -----------------------------------------------------------------

def validate(heats: pd.DataFrame, runs: pd.DataFrame, dog_master: pd.DataFrame) -> pd.DataFrame:
    """Data-quality checks: one row per check, with the count of affected rows."""
    checks = []

    def add(check, n, unit, expected, note=""):
        checks.append({"check": check, "n": int(n), "unit": unit, "expected": expected, "note": note})

    wr = heats[heats["is_wrft"]]
    add("rows", len(heats), "rows", "8571")
    add("wrft_rows", len(wr), "rows", "1128")
    add("rows_realigned", heats["row_realigned"].sum(), "rows", "19", "Step 1.4")
    add("heats_paired", heats.loc[heats["paired"], "heat_id"].nunique(), "heats", "")
    add("rows_unpaired", (~heats["paired"]).sum(), "rows", "", "opponent row missing or practice")
    lanes = heats[heats["paired"]].groupby("heat_id")["lane"].nunique()
    add("paired_heats_same_lane", (lanes != 2).sum(), "heats", "0")
    outcome_pairs = heats[heats["paired"]].groupby("heat_id")["outcome"].agg(lambda s: "/".join(sorted(s.dropna())))
    add("paired_heats_both_win", outcome_pairs.eq("win/win").sum(), "heats", "0")
    add("paired_heats_both_loss", outcome_pairs.eq("loss/loss").sum(), "heats", "",
        "allowed: both teams can lose (UKFL 8.11.M)")
    add("red_font_mismatch_cells", heats["red_font_mismatch"].sum(), "non-empty cells", "0")

    fully_numeric = heats["identity_holds"].notna()
    add("identity_rows", fully_numeric.sum(), "rows", "6286")
    add("identity_holds", heats.loc[fully_numeric, "identity_holds"].sum(), "rows", "~87.7%",
        f"{heats.loc[fully_numeric, 'identity_holds'].mean():.1%} within ±{config.IDENTITY_TOL} s")
    add("rerun_time_negative", heats["rerun_time"].lt(-config.IDENTITY_TOL).sum(), "rows", "",
        "total smaller than its parts")

    for flag in ["is_practice", "is_zero_total", "no_outcome", "has_placeholder_dog0", "is_complete",
                 "is_clean_heat"]:
        add(flag, heats[flag].sum(), "rows", "")

    for flag in ["run_fault", "pass_fault", "run_too_fast", "run_over_ceiling", "run_dog_outlier",
                 "pass_over_ceiling", "valid_speed", "valid_pass", "is_placeholder_dog0"]:
        add(flag, runs[flag].sum(), "dog slots", "")

    wd = runs[runs["is_wrft_dog"]]
    add("wrft_dogs_found", wd["dog_key"].nunique(), "dogs", "50")
    add("wrft_unknown_names", wd["wrft_name_unknown"].sum(), "dog slots", "0")
    missing = sorted(set(dog_master["dog"]) - set(wd["dog_key"]))
    add("master_dogs_never_ran", len(missing), "dogs", "1", ", ".join(missing))

    # Hurdle height = jump height of the smallest WRFT dog that ran.
    ran = wd[wd["run_code"].ne("missing")]
    min_jump = ran.groupby("row_id")["jump_height_cm"].min()
    hurdle = heats.set_index("row_id").loc[min_jump.index, "hurdle_cm"]
    mismatch = hurdle.ne(min_jump) & hurdle.notna()
    heats["hurdle_expected_cm"] = heats["row_id"].map(min_jump)
    heats["hurdle_mismatch"] = heats["row_id"].isin(mismatch[mismatch].index)
    add("wrft_hurdle_mismatch", mismatch.sum(), "rows", "0",
        f"higher than expected: {(hurdle > min_jump).sum()}, lower: {(hurdle < min_jump).sum()}")
    add("wrft_hurdle_missing", hurdle.isna().sum(), "rows", "0")

    young = wd[wd["age_months"] < config.MIN_AGE_MONTHS]
    add("wrft_dog_under_18_months", young["dog_key"].nunique(), "dogs", "0",
        "; ".join(f"{d}: {young[young.dog_key == d].age_months.min():.1f}-"
                  f"{young[young.dog_key == d].age_months.max():.1f} mo, "
                  f"{(young.dog_key == d).sum()} slots" for d in young["dog_key"].unique()))

    teams_per_day = wd.groupby(["date", "dog_key"])["team"].nunique()
    multi = teams_per_day[teams_per_day > 1]
    add("wrft_dog_two_teams_same_day", len(multi), "dog-days", "", "report only")

    dup = wd.groupby("row_id")["dog_key"].apply(lambda s: s.duplicated().any())
    add("wrft_dog_twice_in_one_row", dup.sum(), "rows", "0")
    return pd.DataFrame(checks)


def hurdle_by_dog(heats: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """Per WRFT "height dog": master jump height vs the hurdle actually set.

    The team hurdle should equal the jump height of its smallest dog. For each
    WRFT row, the dog(s) with the lowest master height are the height dogs;
    when the recorded hurdle differs, this counts against them. A dog that is
    consistently raced lower (or higher) than its master height probably had a
    different official height in 2023 (see ANALYSIS_LOG Step 1.9).
    """
    ran = runs[runs["is_wrft_dog"] & runs["run_code"].ne("missing") & runs["hurdle_cm"].notna()]
    team_min = ran.groupby("row_id")["jump_height_cm"].transform("min")
    height_dogs = ran[ran["jump_height_cm"].eq(team_min)]
    hd = height_dogs.assign(
        lower=height_dogs["hurdle_cm"].lt(height_dogs["jump_height_cm"]),
        higher=height_dogs["hurdle_cm"].gt(height_dogs["jump_height_cm"]),
    )
    out = hd.groupby("dog_key").agg(
        jump_height_cm=("jump_height_cm", "first"),
        n_rows_as_height_dog=("row_id", "nunique"),
        n_hurdle_lower=("lower", "sum"),
        n_hurdle_higher=("higher", "sum"),
        typical_hurdle_cm=("hurdle_cm", lambda s: s.mode().iat[0]),
    )
    out["share_mismatch"] = (
        (out["n_hurdle_lower"] + out["n_hurdle_higher"]) / out["n_rows_as_height_dog"]).round(3)
    return out.reset_index().rename(columns={"dog_key": "dog"}).sort_values(
        "share_mismatch", ascending=False, ignore_index=True)


# --- Orchestration -----------------------------------------------------------------

def build_all() -> dict[str, pd.DataFrame]:
    """Run the whole cleaning pipeline and return every output table."""
    dog_master = dogs_mod.load_dogs()
    rows, competitions = build_competitions(excel_reader.read_all())
    heats = parse_times(rows)
    heats = pair_heats(heats)
    heats = flag_heats(heats)
    heats = assign_races(heats)
    runs = flag_runs(build_runs(heats, dog_master))
    quality = validate(heats, runs, dog_master)   # also adds hurdle columns to heats
    return {"competitions": competitions, "heats": heats, "runs": runs,
            "dogs": dog_master, "data_quality": quality,
            "wrft_hurdle_check": hurdle_by_dog(heats, runs)}


HEAT_COLUMNS = [
    "row_id", "heat_id", "race_id", "heat_in_race", "source", "sheet", "sheet_id", "excel_row",
    "row_no", "comp_day_id", "competition", "ring", "venue", "date", "day_index",
    "heat_time", "division", "team", "team_norm", "is_wrft", "opponent", "opponent_norm",
    "opponent_is_wrft", "lane", "outcome", "hurdle_cm", "hurdle_expected_cm", "hurdle_mismatch",
    "total", *config.NAME_COLUMNS, *[c for s in SLOTS for c in (s, f"{s}_code")],
    "clean_time", "rerun_time",
    "identity_holds", "has_rerun", "n_dogs", "n_names", "n_false_start", "n_pass_fault",
    "n_run_fault", "n_faults", "is_complete", "is_clean_heat", "is_practice", "is_zero_total",
    "no_outcome", "has_placeholder_dog0", "paired", "row_realigned", "overflow_value",
    "red_font_mismatch",
]


def write_outputs(tables: dict[str, pd.DataFrame]) -> None:
    """Write the tables to data/processed/ (parquet for the big ones, CSV otherwise)."""
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    tables["competitions"].to_csv(config.PROCESSED / "competitions.csv", index=False)
    tables["dogs"].to_csv(config.PROCESSED / "dogs.csv", index=False)
    tables["data_quality"].to_csv(config.PROCESSED / "data_quality.csv", index=False)
    tables["wrft_hurdle_check"].to_csv(config.PROCESSED / "wrft_hurdle_check.csv", index=False)
    heats = tables["heats"][HEAT_COLUMNS].copy()
    for col in config.NAME_COLUMNS:          # mixed str / int (the "0" names) -> string
        heats[col] = heats[col].map(lambda v: None if pd.isna(v) else str(v)).astype("string")
    heats.to_parquet(config.PROCESSED / "heats.parquet", index=False)
    runs = tables["runs"].copy()
    runs["dog_name_raw"] = runs["dog_name_raw"].astype("string")
    runs.to_parquet(config.PROCESSED / "runs.parquet", index=False)
