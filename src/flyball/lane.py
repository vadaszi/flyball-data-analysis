"""Q1: does the lane colour (red or blue) affect performance?

Under the rules the two lanes are identical (domain_knowledge.md §3), so the
question is whether the real venues break that symmetry (sun, slope, surface
wear, spectators). Choices are explained in ANALYSIS_LOG.md Step 4:

- The lane is drawn once per race: a team keeps its lane for every heat of
  the race, and the first team listed on the sheet is always blue. So lanes
  are compared across races, and standard errors are clustered on race.
- Every effect is "blue minus red", compared within the same unit on the
  same day: the same dog (run, start, pass) or the same team (heat). Rows
  of other days or other dogs never enter a comparison.
- A difference is only worth acting on if it is larger than an equivalence
  margin (MARGINS); the TOST p-value says whether the effect is shown to be
  smaller than that.
"""

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as sps

from flyball import metrics, stats

# Smallest difference that matters to the coach (plan.md, decided 2026-10-13).
MARGINS = {
    "run_s": 0.05,       # seconds per dog run
    "heat_s": 0.20,      # seconds per heat (4 runs)
    "line_s": 0.02,      # seconds per start or pass
    "rate": 0.02,        # 2 percentage points for any rate
}


def add_lane_columns(df: pd.DataFrame) -> pd.DataFrame:
    """`is_blue` (0/1) and the grouping keys used by the within comparisons."""
    out = df.assign(is_blue=df["lane"].eq("blue").astype(float))
    if "dog_key" in out:
        out["dog_day"] = out["dog_key"].astype(str) + "|" + out["comp_day_id"]
    out["team_day"] = out["team_norm"] + "|" + out["comp_day_id"]
    return out


# --- How lanes are assigned ------------------------------------------------------------

def lane_assignment(heats: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Is the lane drawn per heat or per race, and does any WRFT team get one lane more often?

    `summary`: switches of lane inside a race, red/blue balance of race-teams,
    and the lane of the first team listed in each paired heat.
    `wrft_teams`: races per WRFT team in each lane, binomial test against 50 %
    with Holm over the 7 teams.
    """
    h = heats.sort_values(["race_id", "team_norm", "heat_in_race"])
    prev = h.groupby(["race_id", "team_norm"])["lane"].shift()
    consecutive = prev.notna()
    switches = int((h["lane"] != prev)[consecutive].sum())

    race_team = (h.groupby(["race_id", "team_norm"])
                 .agg(lane=("lane", lambda s: s.mode().iat[0]), is_wrft=("is_wrft", "first"))
                 .reset_index())
    view = metrics.heat_view(heats)
    first_listed = view[view["row_id"] < view["opp_row_id"]]
    summary = pd.DataFrame([
        {"check": "lane switches between consecutive heats of the same race",
         "count": switches, "out_of": int(consecutive.sum())},
        {"check": "race-teams in the red lane", "count": int(race_team["lane"].eq("red").sum()),
         "out_of": len(race_team)},
        {"check": "paired heats where the first-listed team is blue",
         "count": int(first_listed["lane"].eq("blue").sum()), "out_of": len(first_listed)},
    ])
    summary["share"] = summary["count"] / summary["out_of"]

    w = race_team[race_team["is_wrft"]]
    teams = w.groupby("team_norm").agg(races=("lane", "size"), red=("lane", lambda s: s.eq("red").sum()))
    teams["red_share"] = teams["red"] / teams["races"]
    teams["p_value"] = [sps.binomtest(int(k), int(n)).pvalue for k, n in zip(teams["red"], teams["races"])]
    teams["p_holm"] = stats.holm(teams["p_value"])
    return {"summary": summary, "wrft_teams": teams.reset_index()}


# --- Dog run time ----------------------------------------------------------------------------

def lane_run_effect(runs: pd.DataFrame, sample: str) -> pd.DataFrame:
    """Blue-minus-red effect on a dog's run time, by two models.

    mixed  : log(run_time) ~ lane + position + hurdle step + ring-day + (1 | dog)
             (the Phase 3 dog model with the lane added)
    within : the same dog on the same ring-day, other terms as above,
             errors clustered on race (lanes are drawn per race)
    The log effect is turned into seconds at the sample's median run time.
    The verdict uses the wider of the two CIs (`within`, in practice).
    """
    d = add_lane_columns(stats.speed_frame(runs))
    median = d["run_time"].median()
    mixed = smf.mixedlm("log_rt ~ is_blue + C(position) + hurdle_step + C(comp_day_id)",
                        d, groups=d["dog_key"]).fit(reml=True)
    within = stats.absorbed_ols(d, "log_rt", ["is_blue", "hurdle_step"], ["dog_day"], "race_id",
                                categorical=("position",))
    rows = []
    for model, tab in (("mixed", stats.mixed_table(mixed, ["is_blue"])),
                       ("within dog-day", within["table"].query("term == 'is_blue'"))):
        est, se = tab["estimate"].iat[0], tab["se"].iat[0]
        rows.append({"sample": sample, "model": model, "runs": len(d), "dogs": d["dog_key"].nunique(),
                     "median_run_s": median, "pct": 100 * est, "seconds": median * est,
                     "ci_low_s": median * tab["ci_low"].iat[0], "ci_high_s": median * tab["ci_high"].iat[0],
                     "p_value": tab["p_value"].iat[0],
                     "p_tost": stats.tost(median * est, median * se, MARGINS["run_s"]).item()})
    out = pd.DataFrame(rows)
    out["verdict"] = stats.verdict(out["p_value"], out["p_tost"])
    return out


def lane_by_ring_day(runs: pd.DataFrame) -> pd.DataFrame:
    """Blue-minus-red run-time effect separately for each ring-day (all dogs).

    One within dog-day model with a lane term per ring-day. A lane asymmetry
    is a property of the venue, so the whole field is used. Each effect is
    in seconds at that ring-day's median run, BH-adjusted over the 28
    ring-days. `attrs["heterogeneity"]` holds the Wald test of "the lane
    effect is the same on every ring-day".
    """
    d = add_lane_columns(stats.speed_frame(runs))
    days = sorted(d["comp_day_id"].unique())
    terms = []
    for day in days:
        col = f"blue_{day}"
        d[col] = d["is_blue"] * d["comp_day_id"].eq(day)
        terms.append(col)
    fit = stats.absorbed_ols(d, "log_rt", [*terms, "hurdle_step"], ["dog_day"], "race_id",
                             categorical=("position",))
    tab = fit["table"].set_index("term").loc[terms]
    median = d.groupby("comp_day_id")["run_time"].median().loc[days].to_numpy()
    out = pd.DataFrame({
        "comp_day_id": days,
        "runs": d.groupby("comp_day_id").size().loc[days].to_numpy(),
        "seconds": median * tab["estimate"].to_numpy(),
        "ci_low_s": median * tab["ci_low"].to_numpy(),
        "ci_high_s": median * tab["ci_high"].to_numpy(),
        "se_s": median * tab["se"].to_numpy(),
        "p_value": tab["p_value"].to_numpy(),
    })
    out["p_bh"] = stats.bh(out["p_value"])
    out["p_tost"] = stats.tost(out["seconds"], out["se_s"], MARGINS["run_s"])
    out["verdict"] = stats.verdict(out["p_bh"], out["p_tost"])
    keys = runs.drop_duplicates("comp_day_id").set_index("comp_day_id")[["competition", "ring", "date"]]
    out = out.join(keys, on="comp_day_id")
    out.attrs["heterogeneity"] = stats.wald_equal(fit["params"], fit["cov"], terms)
    return out


# --- Every other outcome by lane ---------------------------------------------------------

def lane_outcomes(heats: pd.DataFrame, runs: pd.DataFrame, sample: str) -> pd.DataFrame:
    """Blue-minus-red differences on the whole performance profile.

    Heat outcomes compare the same team on the same ring-day; dog outcomes
    the same dog on the same ring-day. Errors are clustered on race. Rates
    are linear-probability differences (0.01 = 1 percentage point). Holm
    over the family; TOST against MARGINS; a plain-language verdict.
    """
    h = add_lane_columns(heats)
    decided = h[h["win_value"].notna()]
    paired = decided[decided["paired"]]
    r = add_lane_columns(runs[runs["dog_key"].notna()])
    starts = r[r["position"].eq(1) & r["pass_code"].ne("missing")]
    passes = r[r["position"].ge(2) & r["pass_code"].ne("missing")]
    starts = starts.assign(t=metrics.ok_imputed(starts["pass_time"], starts["pass_code"], starts["valid_pass"]))
    passes = passes.assign(t=metrics.ok_imputed(passes["pass_time"], passes["pass_code"], passes["valid_pass"]),
                           ok=passes["pass_code"].eq("ok").astype(float))
    speed = add_lane_columns(stats.speed_frame(runs))

    specs = [  # outcome label, frame, column, absorb, margin key, unit
        ("run time (log, per run)", speed, "log_rt", "dog_day", "run_s", "s"),
        ("clean heat time", decided, "clean_time", "team_day", "heat_s", "s"),
        ("start time", starts, "t", "dog_day", "line_s", "s"),
        ("pass time", passes, "t", "dog_day", "line_s", "s"),
        ("pass time, held passes (> 1 s) left out", passes.assign(t=passes["t"].where(passes["t"] <= metrics.HELD_PASS_S)),
         "t", "dog_day", "line_s", "s"),
        ("tight-pass (ok) share", passes, "ok", "dog_day", "rate", "share"),
        ("clean-heat rate", decided, "clean_heat", "team_day", "rate", "share"),
        ("false-start rate (heat)", decided, "any_false_start", "team_day", "rate", "share"),
        ("early-pass rate (heat)", decided, "any_pass_fault", "team_day", "rate", "share"),
        ("run-fault rate (heat)", decided, "any_run_fault", "team_day", "rate", "share"),
        ("heat win rate", paired, "win_value", "team_day", "rate", "share"),
    ]
    rows = []
    for label, frame, col, absorb, margin, unit in specs:
        fit = stats.absorbed_ols(frame.assign(y=frame[col].astype(float)), "y", ["is_blue"], [absorb], "race_id")
        tab = fit["table"].set_index("term").loc["is_blue"]
        scale = speed["run_time"].median() if col == "log_rt" else 1.0     # log effect -> seconds
        raw = frame["run_time" if col == "log_rt" else col].astype(float)
        typical = "median" if unit == "s" else "mean"                  # raw level in each lane
        by_lane = raw.groupby(frame["lane"]).agg(typical)
        rows.append({
            "sample": sample, "outcome": label, "unit": unit, "rows_used": fit["n"],
            "races": fit["n_clusters"], "lane_summary": typical,
            "red": by_lane["red"], "blue": by_lane["blue"],
            "blue_minus_red": scale * tab["estimate"], "ci_low": scale * tab["ci_low"],
            "ci_high": scale * tab["ci_high"], "p_value": tab["p_value"],
            "margin": MARGINS[margin], "p_tost": stats.tost(scale * tab["estimate"], scale * tab["se"],
                                                            MARGINS[margin]).item(),
        })
    out = pd.DataFrame(rows)
    out["p_holm"] = stats.holm(out["p_value"])
    out["verdict"] = stats.verdict(out["p_holm"], out["p_tost"])
    return out


def wrft_dog_lane_medians(runs: pd.DataFrame, min_runs: int = 10) -> pd.DataFrame:
    """Median run time of each WRFT dog in each lane (dogs with enough runs in both)."""
    d = stats.speed_frame(runs[runs["is_wrft_dog"]])
    t = d.pivot_table(index="dog_key", columns="lane", values="run_time", aggfunc=["median", "size"])
    t.columns = [f"{lane}_{'median' if agg == 'median' else 'runs'}" for agg, lane in t.columns]
    t = t[(t["red_runs"] >= min_runs) & (t["blue_runs"] >= min_runs)]
    t["blue_minus_red"] = t["blue_median"] - t["red_median"]
    return t.rename_axis("dog").reset_index().sort_values("red_median", ignore_index=True)
