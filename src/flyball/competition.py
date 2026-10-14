"""Q3: the Phase 3 picture broken down by competition (venue and date).

The unit is a competition day (competition x date): what the coach sees as
"Saturday at Žamberk". Events with two rings are combined per date. Tables
reuse the Phase 3 functions with a competition grouping. Choices are
explained in ANALYSIS_LOG.md Step 4:

- Raw times mix up who ran and where. The dog-adjusted speed index answers
  "how fast did the same dogs run here, compared with an average day", from
  the competition-day effects of the Phase 3 dog model.
- Weather columns are attached for reading only; the weather analysis is 4B.
- Two sheets have no WRFT rows (MED's Trophy, Budějckej xtreme ring 1).
  They appear in the field speed index but not in the WRFT tables.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from flyball import metrics, stats

DAY = ["competition", "date"]
WEATHER_MEAN = ["temp_mean_c", "temp_max_c", "humidity_mean_pct", "wind_mean_ms", "cloud_mean_pct"]
WEATHER_MAX = ["gust_max_ms", "precip_total_mm", "rain_hours", "precip_24h_before_mm"]


# --- Dog-adjusted speed per competition day ---------------------------------------------

def speed_index(runs: pd.DataFrame, sample: str) -> pd.DataFrame:
    """How much faster (-) or slower (+) the same dogs ran on each ring-day, in %.

    Fits the Phase 3 dog model (stats.DOG_RUN_FORMULA, dog random effect) and
    centres the ring-day effects on their average, so 0 % = an average day
    of the season for these dogs. CIs come from the full covariance of the
    ring-day effects.
    """
    d = stats.speed_frame(runs)
    fit = smf.mixedlm(stats.DOG_RUN_FORMULA, d, groups=d["dog_key"]).fit(reml=True)
    levels = sorted(d["comp_day_id"].unique())
    names = [f"C(comp_day_id)[T.{lv}]" for lv in levels[1:]]          # first level is the reference (0)
    b = fit.fe_params[names].to_numpy()
    v = stats.mixed_fe_cov(fit).loc[names, names].to_numpy()
    k = len(levels)
    # Row i of `c` turns the coded effects into "ring-day i minus the average ring-day".
    c = np.zeros((k, k - 1))
    c[1:] = np.eye(k - 1)
    c -= 1.0 / k
    est = c @ b
    se = np.sqrt(np.einsum("ij,jk,ik->i", c, v, c))
    out = pd.DataFrame({
        "comp_day_id": levels, "sample": sample,
        "runs": d.groupby("comp_day_id").size().loc[levels].to_numpy(),
        "dogs": d.groupby("comp_day_id")["dog_key"].nunique().loc[levels].to_numpy(),
        "pct": 100 * (np.exp(est) - 1),
        "ci_low": 100 * (np.exp(est - stats.Z95 * se) - 1),
        "ci_high": 100 * (np.exp(est + stats.Z95 * se) - 1),
        "seconds_at_median": d["run_time"].median() * (np.exp(est) - 1),
    })
    keys = d.drop_duplicates("comp_day_id").set_index("comp_day_id")[["competition", "ring", "date"]]
    return out.join(keys, on="comp_day_id")


def _per_day(df: pd.DataFrame, value: str, weight: str) -> pd.Series:
    """Weighted mean of a ring-day value over the rings of each competition day."""
    w = df[weight]
    return (df[value] * w).groupby([df[c] for c in DAY]).sum() / w.groupby([df[c] for c in DAY]).sum()


# --- WRFT per competition day ------------------------------------------------------------

def competition_days(heats: pd.DataFrame, runs: pd.DataFrame, weather_day: pd.DataFrame,
                     lane_days: pd.DataFrame, index_wrft: pd.DataFrame, index_field: pd.DataFrame) -> pd.DataFrame:
    """One row per competition day with WRFT racing: results, faults, peers, speed, lane, weather.

    - results and profile: metrics.team_summary over all WRFT teams that day
    - why heats were lost: metrics.attribution_summary (avoidable losses)
    - peers: WRFT minus the other teams of the same divisions that day, for
      clean time and win rate (clustered on team, Holm over the days)
    - speed: dog-adjusted index for WRFT dogs and for the field (% vs an
      average day), lane effect (blue minus red, s per run, field)
    - weather over the racing hours (rings of one venue averaged)
    """
    wh, wr = heats[heats["is_wrft"]], runs[runs["is_wrft"]]
    out = metrics.team_summary(wh, wr, DAY).set_index(DAY)
    out.insert(0, "teams", wh.groupby(DAY)["team"].nunique())
    out.insert(1, "venue", wh.groupby(DAY)["venue"].first())

    attr = metrics.fault_attribution(heats)
    attr = metrics.attribution_summary(attr[attr["is_wrft"]], DAY).set_index(DAY)
    out = out.join(attr[["losses", "avoidable_losses", "share_losses_with_fault", "share_losses_avoidable"]])

    decided = heats[heats["win_value"].notna()]
    for metric, col in (("clean_time", "clean_time"), ("win_rate", "win_value")):
        gaps = {key: stats.within_division_gap(day, col, day["is_wrft"])
                for key, day in decided.groupby(DAY) if key in out.index}
        gaps = pd.DataFrame(gaps).T
        out[f"peer_gap_{metric}"] = gaps["estimate"]
        out[f"peer_gap_{metric}_ci_low"] = gaps["ci_low"]
        out[f"peer_gap_{metric}_ci_high"] = gaps["ci_high"]
        out[f"peer_gap_{metric}_p_holm"] = stats.holm(gaps["p_value"].astype(float).reindex(out.index))

    for name, idx in (("wrft", index_wrft), ("field", index_field)):
        out[f"speed_index_{name}_pct"] = _per_day(idx, "pct", "runs")
    out["lane_blue_minus_red_s"] = _per_day(lane_days.assign(w=1 / lane_days["se_s"] ** 2), "seconds", "w")

    wx = weather_day.assign(date=pd.to_datetime(weather_day["date"]))
    wx = wx.groupby(DAY).agg({**{c: "mean" for c in WEATHER_MEAN}, **{c: "max" for c in WEATHER_MAX}})
    out = out.join(wx)
    return out.reset_index().sort_values("date", ignore_index=True)


def competition_teams(heats: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """One row per WRFT team x competition (both days): results and division rank.

    The rank is by median clean time within the team's main division at
    that competition (the one it raced most heats in).
    """
    wh, wr = heats[heats["is_wrft"]], runs[runs["is_wrft"]]
    out = metrics.team_summary(wh, wr, ["competition", "team"])
    ranks = metrics.division_ranks(heats)
    ranks["competition"] = ranks["comp_div"].str.split(" | div ", regex=False).str[0]
    ranks["division"] = ranks["comp_div"].str.split(" | div ", regex=False).str[1].astype(int)
    main = (ranks.sort_values("heats", ascending=False).drop_duplicates(["competition", "team"])
            [["competition", "team", "division", "rank", "teams_in_div", "gap_to_div_median"]])
    out = out.merge(main, on=["competition", "team"], how="left")
    first_date = wh.groupby("competition")["date"].min().rename("first_date")
    return out.join(first_date, on="competition").sort_values(["first_date", "team"], ignore_index=True)


def dog_by_competition(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per WRFT dog x competition: speed against its own season median, passes, faults.

    `vs_season_s` < 0 means the dog ran faster there than its season
    median. It is descriptive: hurdle height and position can differ between
    competitions (the dog model handles those).
    """
    w = runs[runs["is_wrft_dog"]]
    valid = w[w["valid_speed"]]
    season = valid.groupby("dog_key")["run_time"].median()
    passes = w[w["position"].ge(2) & w["pass_code"].ne("missing")]
    key = ["dog_key", "competition"]
    out = pd.DataFrame({
        "slots": w.groupby(key).size(),
        "valid_runs": valid.groupby(key).size(),
        "median_run": valid.groupby(key)["run_time"].median(),
        "median_pass": passes[passes["valid_pass"]].groupby(key)["pass_time"].median(),   # ok counts as 0
        "ok_pass_share": passes["pass_code"].eq("ok").groupby([passes[k] for k in key]).mean(),
        "faults": (w["run_fault"] | w["pass_fault"]).groupby([w[k] for k in key]).sum(),
        "first_date": w.groupby(key)["date"].min(),
    })
    out["valid_runs"] = out["valid_runs"].fillna(0).astype(int)
    out = out.join(season.rename("season_median"), on="dog_key")
    out["vs_season_s"] = out["median_run"] - out["season_median"]
    return out.rename_axis(["dog", "competition"]).reset_index().sort_values(["dog", "first_date"],
                                                                              ignore_index=True)


# --- Season trend ---------------------------------------------------------------------------

def season_trend(runs: pd.DataFrame, sample: str) -> pd.DataFrame:
    """Did the same dogs get faster over the season? % change in run time per 30 days.

    log(run_time) ~ days since the first competition + position + hurdle
    step + (1 | dog). No competition-day effects (they would absorb the
    trend), so the trend also carries venue and weather: cold days are in
    April, May and October, so it is separated from temperature in 4B.
    """
    d = stats.speed_frame(runs)
    d["months"] = (pd.to_datetime(d["date"]) - pd.to_datetime(d["date"]).min()).dt.days / 30
    fit = smf.mixedlm("log_rt ~ months + C(position) + hurdle_step", d, groups=d["dog_key"]).fit(reml=True)
    t = stats.mixed_table(fit, ["months"]).iloc[0]
    return pd.DataFrame([{
        "sample": sample, "runs": len(d), "dogs": d["dog_key"].nunique(),
        "pct_per_30_days": 100 * (np.exp(t["estimate"]) - 1),
        "ci_low": 100 * (np.exp(t["ci_low"]) - 1), "ci_high": 100 * (np.exp(t["ci_high"]) - 1),
        "seconds_per_30_days": d["run_time"].median() * (np.exp(t["estimate"]) - 1),
        "p_value": t["p_value"],
    }])
