"""Phase 3 metrics: the coach's "general picture" for teams and dogs.

Every function takes the processed tables (data/processed/) and returns a
DataFrame, so the script, the notebook and the tests share one implementation.
Choices are explained in ANALYSIS_LOG.md Step 2. The main ones:

- Practice rows are dropped on load. Speed uses `valid_speed` runs and
  `valid_pass` passes/starts (Phase 2 flags).
- Divisions are numbered per competition, so the peer group of a team is
  its competition x division (`comp_div`).
- Ties count as half a win in win rates.
- `ok` passes are a censored code ("tight pass, under about 0.08 s, value not
  shown"): medians treat them as 0, means use OK_PASS_IMPUTE.
"""

import numpy as np
import pandas as pd

from flyball import config, stats

OK_PASS_IMPUTE = 0.04       # mid-point of the ~0-0.08 s range an `ok` pass stands for
HELD_PASS_S = 1.0           # robustness checks: a slower pass was probably held back on purpose
TIE_WIN_VALUE = 0.5


# --- Loading ------------------------------------------------------------------------

def load_processed() -> dict[str, pd.DataFrame]:
    """The Phase 2 tables, without practice rows, plus the `comp_div` peer group."""
    heats = pd.read_parquet(config.PROCESSED / "heats.parquet")
    runs = pd.read_parquet(config.PROCESSED / "runs.parquet")
    heats = heats[~heats["is_practice"]].reset_index(drop=True)
    runs = runs[~runs["is_practice"]].reset_index(drop=True)
    for df in (heats, runs):
        df["comp_div"] = df["competition"] + " | div " + df["division"].astype(str)
    return {
        "heats": add_heat_columns(heats),
        "runs": runs,
        "dogs": pd.read_csv(config.PROCESSED / "dogs.csv"),
        "competitions": pd.read_csv(config.PROCESSED / "competitions.csv"),
        "hurdle_check": pd.read_csv(config.PROCESSED / "wrft_hurdle_check.csv"),
    }


def add_heat_columns(heats: pd.DataFrame) -> pd.DataFrame:
    """Heat-level helper columns used throughout Phase 3."""
    h = heats.copy()
    h["win_value"] = h["outcome"].map({"win": 1.0, "tie": TIE_WIN_VALUE, "loss": 0.0})
    h["rerun"] = h["has_rerun"].fillna(False).astype(bool)
    h["any_fault"] = h["n_faults"].gt(0)
    # A clean heat: all 4 dogs ran, no coded fault and no hidden rerun time.
    h["clean_heat"] = h["is_complete"] & ~h["any_fault"] & ~h["rerun"]
    h["any_false_start"] = h["n_false_start"].gt(0)
    h["any_pass_fault"] = h["n_pass_fault"].gt(0)
    h["any_run_fault"] = h["n_run_fault"].gt(0)
    valid_start = h["start_code"].eq("number") & h["start"].between(0, config.MAX_START)
    h["start_valid"] = h["start"].where(valid_start)
    h["rerun_seconds"] = h["rerun_time"].where(h["rerun"], 0.0).where(h["identity_holds"].notna())
    # Typical strength of the team on that day, leaving the heat itself out.
    day_team = [h["comp_day_id"], h["team_norm"]]
    h["typ_clean_time"] = loo_median(h["clean_time"], day_team)
    h["typ_start"] = loo_median(h["start_valid"], day_team)
    h["typ_clean_total"] = loo_median(h["total"].where(h["clean_heat"]), day_team)
    return h


def ok_imputed(times: pd.Series, codes: pd.Series, valid: pd.Series) -> pd.Series:
    """Start/pass time for fault-free attempts, `ok` counted as OK_PASS_IMPUTE."""
    return times.where(valid).mask(codes.eq("ok") & valid, OK_PASS_IMPUTE)


def loo_median(values: pd.Series, by) -> pd.Series:
    """Leave-one-out median within groups: for each row, the median of the
    other rows of its group (NaN values are ignored)."""
    def one_group(s: pd.Series) -> pd.Series:
        v = s.to_numpy(dtype=float)
        out = np.full(len(v), np.nan)
        for i in range(len(v)):
            others = np.delete(v, i)
            others = others[~np.isnan(others)]
            if len(others):
                out[i] = np.median(others)
        return pd.Series(out, index=s.index)
    return values.groupby(by, group_keys=False).apply(one_group)


# --- Heats seen from both sides -----------------------------------------------------

OPP_COLUMNS = ["row_id", "team_norm", "outcome", "total", "typ_clean_time", "typ_start",
               "any_false_start", "any_pass_fault", "any_run_fault", "any_fault", "clean_heat"]


def heat_view(heats: pd.DataFrame) -> pd.DataFrame:
    """Paired heats only, one row per team, with the opponent's columns as `opp_*`."""
    paired = heats[heats["paired"]]
    opp = paired[["heat_id", *OPP_COLUMNS]].rename(columns={c: f"opp_{c}" for c in OPP_COLUMNS})
    view = paired.merge(opp, on="heat_id")
    return view[view["row_id"] != view["opp_row_id"]].reset_index(drop=True)


def heat_model_frame(view: pd.DataFrame, wrft_focal: bool = False) -> pd.DataFrame:
    """One row per decided heat, from a focal team's side, for the heat-win model.

    Focal team: the WRFT team when `wrft_focal` (WRFT-only fit), otherwise the
    first row of the pair in sheet order (an arbitrary but fixed choice; the
    gaps are differences, so the model is symmetric). Ties and heats without
    a result are left out.
    """
    v = view[view["outcome"].isin(["win", "loss"])]
    if wrft_focal:
        v = v[v["is_wrft"] & (~v["opponent_is_wrft"] | (v["row_id"] < v["opp_row_id"]))]
    else:
        v = v[v["row_id"] < v["opp_row_id"]]
    out = pd.DataFrame({
        "heat_id": v["heat_id"], "race_id": v["race_id"], "team_norm": v["team_norm"],
        "comp_div": v["comp_div"], "is_wrft": v["is_wrft"],
        "win": v["outcome"].eq("win").astype(int),
        "both_lost": v["outcome"].eq("loss") & v["opp_outcome"].eq("loss"),
        "speed_gap": v["typ_clean_time"] - v["opp_typ_clean_time"],
        "start_gap": v["typ_start"] - v["opp_typ_start"],
    })
    for side, prefix in (("own", ""), ("opp", "opp_")):
        for f in ("false_start", "pass_fault", "run_fault"):
            out[f"{side}_{f}"] = v[f"{prefix}any_{f}"].astype(int)
    return out.reset_index(drop=True)


def win_by_fault_status(view: pd.DataFrame) -> pd.DataFrame:
    """Win rate by (own heat clean?, opponent heat clean?), from both sides."""
    v = view[view["outcome"].isin(["win", "loss"])]
    t = v.assign(own=np.where(v["any_fault"], "own fault", "own clean"),
                 opp=np.where(v["opp_any_fault"], "opponent fault", "opponent clean"))
    out = t.groupby(["own", "opp"]).agg(team_heats=("win_value", "size"), win_rate=("win_value", "mean"))
    lo, hi = stats.wilson_ci(out["win_rate"] * out["team_heats"], out["team_heats"])
    return out.assign(ci_low=lo, ci_high=hi).reset_index()


def win_by_speed_gap(view: pd.DataFrame, bins=(-np.inf, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, np.inf)) -> pd.DataFrame:
    """In heats where both teams ran clean: win rate by typical-speed gap (s)."""
    v = view[view["outcome"].isin(["win", "loss"]) & view["clean_heat"] & view["opp_clean_heat"]]
    gap = v["typ_clean_time"] - v["opp_typ_clean_time"]
    t = v.assign(gap_bin=pd.cut(gap, bins)).dropna(subset=["gap_bin"])
    out = t.groupby("gap_bin", observed=True).agg(team_heats=("win_value", "size"),
                                                  win_rate=("win_value", "mean"))
    lo, hi = stats.wilson_ci(out["win_rate"] * out["team_heats"], out["team_heats"])
    return out.assign(ci_low=lo, ci_high=hi).reset_index().astype({"gap_bin": str})


# --- Why heats are won and lost ------------------------------------------------------

OUTCOME_LABELS = {
    "win_clean": "Won, clean",
    "win_after_fault": "Won despite a fault (corrected)",
    "loss_fault": "Lost, own fault",
    "loss_uncoded_rerun": "Lost, rerun without a coded fault",
    "loss_slower": "Lost, clean but slower",
    "loss_breakout_like": "Lost, clean, both teams lost (break-out?)",
    "loss_not_finished": "Lost, not all dogs finished, no coded fault",
}


def fault_attribution(heats: pd.DataFrame) -> pd.DataFrame:
    """Label every decided team row with why it was won or lost.

    `avoidable` marks faulted losses that the team would probably have won
    clean: its typical clean total that day (leave-one-out) beats the
    opponent's actual winning total.
    """
    h = heats[heats["outcome"].isin(["win", "loss"])].copy()
    opp = heat_view(heats).set_index("row_id")[["opp_outcome", "opp_total"]]
    h = h.join(opp, on="row_id")
    win, fault, rerun = h["outcome"].eq("win"), h["any_fault"], h["rerun"]
    both_lost = h["opp_outcome"].eq("loss")
    h["reason"] = np.select(
        [win & ~fault & ~rerun, win, fault, rerun,
         h["is_complete"] & both_lost, h["is_complete"]],
        ["win_clean", "win_after_fault", "loss_fault", "loss_uncoded_rerun",
         "loss_breakout_like", "loss_slower"],
        default="loss_not_finished")
    h["avoidable"] = (h["reason"].eq("loss_fault") & h["opp_outcome"].eq("win")
                      & h["typ_clean_total"].lt(h["opp_total"]))
    return h


def attribution_summary(attr: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Share of each outcome reason, plus avoidable losses, per group."""
    counts = pd.crosstab([attr[g] for g in group], attr["reason"]).reindex(
        columns=list(OUTCOME_LABELS), fill_value=0)
    out = counts.copy()
    out.insert(0, "heats", counts.sum(axis=1))
    losses = counts.filter(like="loss").sum(axis=1)
    out["losses"] = losses
    out["avoidable_losses"] = attr.groupby(group)["avoidable"].sum()
    out["share_losses_with_fault"] = (counts["loss_fault"] + counts["loss_uncoded_rerun"]) / losses
    out["share_losses_avoidable"] = out["avoidable_losses"] / losses
    return out.reset_index()


def fault_cost_seconds(heats: pd.DataFrame) -> pd.DataFrame:
    """What one corrected fault costs in seconds, and how often one fault loses the heat.

    Uses heats with exactly one coded fault of the given kind and nothing else.
    `rerun_seconds_median`: extra time in the total when the fault was
    corrected (only computable where all parts are numeric).
    """
    decided = heats[heats["outcome"].isin(["win", "loss"])]
    single = {
        "false_start": decided["n_false_start"].eq(1) & decided["n_faults"].eq(1),
        "pass_fault": decided["n_pass_fault"].eq(1) & decided["n_faults"].eq(1),
        "run_fault": decided["n_run_fault"].eq(1) & decided["n_faults"].eq(1),
        "none": decided["clean_heat"],
    }
    rows = []
    for kind, mask in single.items():
        d = decided[mask]
        corrected = d[d["rerun"]]
        rows.append({"fault": kind, "team_heats": len(d),
                     "loss_rate": d["outcome"].eq("loss").mean(),
                     "corrected_n": len(corrected),
                     "rerun_seconds_median": corrected["rerun_time"].median()})
    return pd.DataFrame(rows)


# --- Team level -----------------------------------------------------------------------

def team_summary(heats: pd.DataFrame, runs: pd.DataFrame, group: list[str]) -> pd.DataFrame:
    """Win rate, speed, start/pass profile, fault rates and rerun cost per group."""
    decided = heats[heats["win_value"].notna()]
    g = decided.groupby(group)
    out = pd.DataFrame({
        "heats": g.size(),
        "win_rate": g["win_value"].mean(),
        "clean_heat_rate": g["clean_heat"].mean(),
        "median_clean_time": g["clean_time"].median(),
        "best_clean_time": g["clean_time"].min(),
        "false_start_rate": g["any_false_start"].mean(),
        "heat_pass_fault_rate": g["any_pass_fault"].mean(),
        "heat_run_fault_rate": g["any_run_fault"].mean(),
        "rerun_seconds_per_heat": g["rerun_seconds"].mean(),
    })
    out["win_ci_low"], out["win_ci_high"] = stats.wilson_ci(out["win_rate"] * out["heats"], out["heats"])

    r = runs[runs["outcome"].notna()]
    starts, passes = r[r["position"].eq(1)], r[r["position"].ge(2) & r["pass_code"].ne("missing")]
    out["median_start"] = starts[starts["valid_pass"]].groupby(group)["pass_time"].median()
    out["median_pass"] = passes[passes["valid_pass"]].groupby(group)["pass_time"].median()
    out["ok_pass_share"] = passes.groupby(group)["pass_code"].apply(lambda s: s.eq("ok").mean())
    out["pass_fault_rate"] = passes.groupby(group)["pass_fault"].mean()
    out["median_run"] = r[r["valid_speed"]].groupby(group)["run_time"].median()
    return out.reset_index()


PEER_METRICS = {        # metric name: heat-level column
    "clean_time_s": "clean_time",
    "win_rate": "win_value",
    "clean_heat_rate": "clean_heat",
    "false_start_rate": "any_false_start",
    "pass_fault_rate": "any_pass_fault",
    "run_fault_rate": "any_run_fault",
}


def peer_benchmark(heats: pd.DataFrame) -> pd.DataFrame:
    """Each WRFT team against the other teams of the divisions it raced in.

    One row per WRFT team x metric: the within-division difference (team
    minus peers) with a 95 % CI clustered on team, and a Holm-adjusted
    p-value over the whole family (7 teams x 6 metrics). Rates are 0/1
    outcomes, so differences read as percentage points / 100.
    """
    decided = heats[heats["win_value"].notna()].copy()
    decided["clean_heat"] = decided["clean_heat"].astype(float)
    for col in ("any_false_start", "any_pass_fault", "any_run_fault"):
        decided[col] = decided[col].astype(float)
    rows = []
    for team in sorted(decided.loc[decided["is_wrft"], "team"].unique()):
        for metric, col in PEER_METRICS.items():
            res = stats.within_division_gap(decided, col, decided["team"].eq(team))
            rows.append({"team": team, "metric": metric, **res})
    out = pd.DataFrame(rows)
    out["p_holm"] = stats.holm(out["p_value"])
    return out


def division_ranks(heats: pd.DataFrame) -> pd.DataFrame:
    """Rank of every WRFT team by median clean time within each comp_div it raced."""
    decided = heats[heats["win_value"].notna()]
    per_team = decided.groupby(["comp_div", "team"]).agg(
        is_wrft=("is_wrft", "first"), heats=("win_value", "size"),
        win_rate=("win_value", "mean"), median_clean_time=("clean_time", "median"),
        clean_heat_rate=("clean_heat", "mean"))
    per_team["rank"] = per_team.groupby("comp_div")["median_clean_time"].rank(method="min")
    per_team["teams_in_div"] = per_team.groupby("comp_div")["heats"].transform("size")
    per_team["div_median_clean_time"] = per_team.groupby("comp_div")["median_clean_time"].transform("median")
    per_team["gap_to_div_median"] = per_team["median_clean_time"] - per_team["div_median_clean_time"]
    return per_team[per_team["is_wrft"]].drop(columns="is_wrft").reset_index()


# --- Starts and passes: the risk trade-off -------------------------------------------------

def pass_profile(runs: pd.DataFrame, kind: str, min_attempts: int = 20) -> pd.DataFrame:
    """Per dog: how tight it starts or passes, and how often it faults.

    kind = "start" (position 1, fault = false start) or "pass" (positions
    2-4, fault = early pass). `mean_time_s` is the average time lost on the
    line in a fault-free attempt (`ok` = OK_PASS_IMPUTE, held-back passes
    over the ceiling excluded).
    """
    attempts = runs[runs["pass_code"].ne("missing") & runs["dog_key"].notna()]
    attempts = attempts[attempts["position"].eq(1) if kind == "start" else attempts["position"].ge(2)]
    timed = attempts["pass_time"].where(attempts["valid_pass"])
    imputed = timed.mask(attempts["pass_code"].eq("ok"), OK_PASS_IMPUTE)
    g = attempts.assign(t=timed, ti=imputed, ok=attempts["pass_code"].eq("ok")).groupby("dog_key")
    out = pd.DataFrame({
        "is_wrft_dog": g["is_wrft_dog"].first(),
        "attempts": g.size(),
        "faults": g["pass_fault"].sum(),
        "median_time_s": g["t"].median(),
        "mean_time_s": g["ti"].mean(),
        "ok_share": g["ok"].mean(),
    })
    out["fault_rate"] = out["faults"] / out["attempts"]
    return out[out["attempts"] >= min_attempts].reset_index()


PASS_BINS = {
    "start": [0, 0.05, 0.08, 0.11, 0.14, 0.18, 0.25, np.inf],
    "pass": [-np.inf, 0.08, 0.12, 0.16, 0.20, 0.25, 0.35, np.inf],
}


def pass_window(profile: pd.DataFrame, kind: str, fault_cost_s: float) -> pd.DataFrame:
    """Dogs binned by how tight they run the line: fault rate and expected cost.

    expected_cost_s = mean time lost on the line + fault rate x fault cost,
    i.e. the average seconds a start/pass costs the team, counting a fault
    as a corrected rerun. The bin with the lowest cost is the "window".
    This is a between-dog comparison, so it is descriptive.
    """
    p = profile.assign(bin=pd.cut(profile["median_time_s"], PASS_BINS[kind]))
    out = p.groupby("bin", observed=True).agg(
        dogs=("dog_key", "size"), attempts=("attempts", "sum"), faults=("faults", "sum"),
        median_time_s=("median_time_s", "median"), mean_time_s=("mean_time_s", "mean"))
    out["fault_rate"] = out["faults"] / out["attempts"]
    out["fault_ci_low"], out["fault_ci_high"] = stats.wilson_ci(out["faults"], out["attempts"])
    out["expected_cost_s"] = out["mean_time_s"] + out["fault_rate"] * fault_cost_s
    out["is_window"] = out["expected_cost_s"].eq(out["expected_cost_s"].min())
    out.insert(0, "kind", kind)
    return out.reset_index().astype({"bin": str})


# --- Dog level ------------------------------------------------------------------------

def dog_scorecard(runs: pd.DataFrame, dogs: pd.DataFrame) -> pd.DataFrame:
    """One row per WRFT dog: speed, consistency, start, pass and fault profile.

    Rates come with Wilson 95 % CIs and an empirical-Bayes shrunken value
    (`*_eb`), which is the one to rank dogs by.
    """
    w = runs[runs["is_wrft_dog"]]
    valid = w[w["valid_speed"]]
    starts = w[w["position"].eq(1) & w["pass_code"].ne("missing")]
    passes = w[w["position"].ge(2) & w["pass_code"].ne("missing")]
    ran = w[w["run_code"].ne("missing")]

    def mad(s):
        return (s - s.median()).abs().median()

    card = pd.DataFrame({
        "slots": w.groupby("dog_key").size(),
        "teams": w.groupby("dog_key")["team"].nunique(),
        "competitions": w.groupby("dog_key")["competition"].nunique(),
        "valid_runs": valid.groupby("dog_key").size(),
        "median_run": valid.groupby("dog_key")["run_time"].median(),
        "best_run_p05": valid.groupby("dog_key")["run_time"].quantile(0.05),
        "run_mad": valid.groupby("dog_key")["run_time"].agg(mad),
        "usual_hurdle_cm": w.groupby("dog_key")["hurdle_cm"].agg(lambda s: s.mode().iat[0]),
        "usual_position": w.groupby("dog_key")["position"].agg(lambda s: s.mode().iat[0]),
        "starts": starts.groupby("dog_key").size(),
        "false_starts": starts.groupby("dog_key")["pass_fault"].sum(),
        "median_start": starts[starts["valid_pass"]].groupby("dog_key")["pass_time"].median(),
        "passes": passes.groupby("dog_key").size(),
        "early_passes": passes.groupby("dog_key")["pass_fault"].sum(),
        "median_pass": passes[passes["valid_pass"]].groupby("dog_key")["pass_time"].median(),
        "ok_pass_share": passes.groupby("dog_key")["pass_code"].apply(lambda s: s.eq("ok").mean()),
        "runs_attempted": ran.groupby("dog_key").size(),
        "run_faults": ran.groupby("dog_key")["run_fault"].sum(),
    })
    counts = ["valid_runs", "starts", "false_starts", "passes", "early_passes", "runs_attempted", "run_faults"]
    card[counts] = card[counts].fillna(0).astype(int)

    for name, k, n in (("false_start", "false_starts", "starts"),
                       ("early_pass", "early_passes", "passes"),
                       ("run_fault", "run_faults", "runs_attempted")):
        with np.errstate(invalid="ignore", divide="ignore"):
            card[f"{name}_rate"] = card[k] / card[n]
        card[f"{name}_ci_low"], card[f"{name}_ci_high"] = stats.wilson_ci(card[k], card[n])
        card[f"{name}_eb"] = stats.eb_shrink_rate(card[k], card[n])

    # Faults of any kind per line crossing or run, the dog's overall reliability.
    total_k = card[["false_starts", "early_passes", "run_faults"]].sum(axis=1)
    total_n = card[["starts", "passes", "runs_attempted"]].sum(axis=1)
    card["any_fault_eb"] = stats.eb_shrink_rate(total_k, total_n)

    attrs = dogs.set_index("dog")[["breed_group", "category", "jump_height_cm"]]
    card = card.join(attrs).rename_axis("dog").reset_index()
    return card.sort_values("median_run", ignore_index=True)


def sensitivity(heats: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """How much headline numbers move when an exclusion rule is switched off or changed."""
    rows = []

    def add(check, baseline, variant, note=""):
        rows.append({"check": check, "baseline": baseline, "variant": variant,
                     "delta": variant - baseline, "note": note})

    w = heats[heats["is_wrft"] & heats["outcome"].notna()]
    base_wr = w["win_value"].mean()
    add("WRFT win rate: drop WRFT-vs-WRFT heats", base_wr, w.loc[~w["opponent_is_wrft"], "win_value"].mean())
    add("WRFT win rate: drop ties", base_wr, w.loc[w["outcome"].ne("tie"), "win_value"].mean())
    add("WRFT win rate: paired heats only", base_wr, w.loc[w["paired"], "win_value"].mean())

    wd = runs[runs["is_wrft_dog"]]
    for label, flag, value, base_mask in (
            ("dog median run: keep per-dog outliers", "run_dog_outlier", "run_time", wd["valid_speed"]),
            ("dog median pass: keep held passes > 3 s", "pass_over_ceiling", "pass_time",
             wd["valid_pass"] & wd["position"].ge(2))):
        base = wd[base_mask].groupby("dog_key")[value].median()
        variant_mask = (base_mask | wd[flag]) & (wd["position"].ge(2) if value == "pass_time" else True)
        var = wd[variant_mask].groupby("dog_key")[value].median()
        diff = (var - base).abs()
        add(f"{label} (median |change| over dogs)", 0.0, diff.median(), f"max {diff.max():.3f} s")
    return pd.DataFrame(rows)
