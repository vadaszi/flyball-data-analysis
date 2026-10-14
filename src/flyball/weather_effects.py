"""Phase 4B (4d): does the weather change how fast and how cleanly the dogs run?

The coach suspects temperature, wind, humidity and rain. Weather is tangled
up with venue and season (the cold days are in April, May and October), so
the main comparison is *within a competition*: the same dog at the same
event, Saturday vs Sunday and morning vs afternoon. Choices are explained in
ANALYSIS_LOG.md Step 5:

- one model term per coach factor, scaled to a realistic change (TERMS);
  temperature has a hinge at HINGE_C, so warm weather may cost more than
  cool weather gains;
- `run_no_today` (the dog's n-th run that day) keeps fatigue apart from the
  afternoon warmth, and `day2` (second day of the event) keeps the
  Saturday/Sunday difference in faults apart from the weather: Sundays were
  mostly cooler, and without this control a "warmer = more faults" signal
  appeared that was really a first-day effect;
- errors are clustered on the venue-day (both rings share one weather) and
  use t(G - 1) critical values, because there are only 22 venue-days;
- verdicts use the 4A equivalence margins (lane.MARGINS) and stats.verdict.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.model_selection import LeaveOneGroupOut
from statsmodels.stats.outliers_influence import variance_inflation_factor

from flyball import config, lane, metrics, stats, weather

HINGE_C = 20.0       # temperature (°C) above which the warm-weather slope applies
WET_MM = 0.1         # rain in the last 3 h that makes the ground "wet" (one rain hour)

# Model terms, each scaled to a realistic change during the season.
TERMS = ["temp10", "hot10", "hum20", "wind3", "wet"]

# What the coach asks about, as combinations of the terms: label -> (factor, weights).
CONTRASTS = {
    "temperature +10 °C (below 20 °C)": ("temperature", {"temp10": 1.0}),
    "temperature +10 °C (above 20 °C)": ("temperature", {"temp10": 1.0, "hot10": 1.0}),
    "humidity +20 pp": ("humidity", {"hum20": 1.0}),
    "wind +3 m/s": ("wind", {"wind3": 1.0}),
    "rain in the last 3 h": ("rain", {"wet": 1.0}),
}
DOG_CONTROLS = ["hurdle_step", "run_no_today", "day2"]          # plus C(position)
TEAM_CONTROLS = ["hurdle_step", "heat_no_today", "day2"]
CONTROL_LABELS = {"day2": "second day of the event", "run_no_today": "each earlier run that day (dog)",
                  "heat_no_today": "each earlier heat that day (team)", "hurdle_step": "hurdle +2.5 cm"}
WEATHER_COLUMNS = ["temp_c", "humidity_pct", "wind_ms", "precip_3h_mm", "precip_24h_mm", "gust_ms"]


# --- Analysis frames ------------------------------------------------------------------

def add_terms(df: pd.DataFrame, hinge: float = HINGE_C, temp: str = "temp_c",
              rain: str = "precip_3h_mm", wet_mm: float = WET_MM) -> pd.DataFrame:
    """The model terms. temp10 is centred on the hinge, so its coefficient is the
    slope below the hinge and temp10 + hot10 the slope above it."""
    return df.assign(
        temp10=(df[temp] - hinge) / 10,
        hot10=(df[temp] - hinge).clip(lower=0) / 10,
        hum20=(df["humidity_pct"] - 60) / 20,
        wind3=df["wind_ms"] / 3,
        wet=df[rain].ge(wet_mm).astype(float),
    )


SEASON_START = pd.Timestamp("2023-04-22")    # first competition day


def _keys(df: pd.DataFrame) -> pd.DataFrame:
    """Venue-day (the cluster: both rings share one weather), months into the season, hour of day."""
    date = pd.to_datetime(df["date"])
    return df.assign(
        venue_day=df["venue"] + "|" + date.dt.strftime("%Y-%m-%d"),
        months=(date - SEASON_START).dt.days / 30,
        day2=(date > date.groupby(df["competition"]).transform("min")).astype(float),
        hour=df["heat_time"].dt.hour + df["heat_time"].dt.minute / 60,
    )


def run_frame(runs: pd.DataFrame, heat_wx: pd.DataFrame) -> pd.DataFrame:
    """Every slot of a known dog, with heat weather, model terms and grouping keys.

    `run_no_today` counts the dog's slots that day in heat order (1 = first run).
    """
    r = runs[runs["dog_key"].notna()].sort_values(["dog_key", "date", "heat_time", "row_id"])
    r = r.assign(run_no_today=r.groupby(["dog_key", "date"]).cumcount() + 1,
                 hurdle_step=(r["hurdle_cm"] - 25.0) / 2.5)
    venue = heat_wx.drop_duplicates("heat_id").set_index("heat_id")["venue"]
    r = r.assign(venue=r["heat_id"].map(venue))
    r = add_terms(_keys(weather.attach(r, heat_wx)))
    r["dog_event"] = r["dog_key"] + "|" + r["competition"]
    r["dog_day"] = r["dog_key"] + "|" + r["comp_day_id"]
    return r.sort_index()


def heat_frame(heats: pd.DataFrame, heat_wx: pd.DataFrame) -> pd.DataFrame:
    """Decided heats with weather, model terms and keys; `heat_no_today` per team and date."""
    h = heats[heats["win_value"].notna()].sort_values(["team_norm", "date", "heat_time", "row_id"])
    h = h.assign(heat_no_today=h.groupby(["team_norm", "date"]).cumcount() + 1,
                 hurdle_step=(h["hurdle_cm"] - 25.0) / 2.5,
                 clean_time_clean=h["clean_time"].where(h["clean_heat"]))
    h = add_terms(_keys(weather.attach(h, heat_wx)))
    h["team_event"] = h["team_norm"] + "|" + h["competition"]
    h["team_day"] = h["team_norm"] + "|" + h["comp_day_id"]
    return h.sort_index()


def outcome_specs(runs_wx: pd.DataFrame, heats_wx: pd.DataFrame) -> list[dict]:
    """Every outcome the weather is tested on: dog-level and team-level."""
    r = runs_wx
    speed = r[r["valid_speed"] & r["hurdle_cm"].notna()].assign(y=lambda x: np.log(x["run_time"]))
    starts = r[r["position"].eq(1) & r["pass_code"].ne("missing")]
    passes = r[r["position"].ge(2) & r["pass_code"].ne("missing")]
    start_t = metrics.ok_imputed(starts["pass_time"], starts["pass_code"], starts["valid_pass"])
    pass_t = metrics.ok_imputed(passes["pass_time"], passes["pass_code"], passes["valid_pass"])
    ran = r[r["run_code"].ne("missing")]
    dog = dict(level="dog", absorb="dog_event", controls=DOG_CONTROLS, categorical=("position",))
    team = dict(level="team", absorb="team_event", controls=TEAM_CONTROLS, categorical=())
    return [
        dict(outcome="run time", frame=speed, unit="log", margin="run_s", **dog),
        dict(outcome="start time", frame=starts.assign(y=start_t.where(start_t <= metrics.HELD_PASS_S)),
             unit="s", margin="line_s", **dog),
        dict(outcome="racing pass time", frame=passes.assign(y=pass_t.where(pass_t <= metrics.HELD_PASS_S)),
             unit="s", margin="line_s", **dog),
        dict(outcome="false-start rate", frame=starts.assign(y=starts["pass_fault"].astype(float)),
             unit="share", margin="rate", **dog),
        dict(outcome="early-pass rate", frame=passes.assign(y=passes["pass_fault"].astype(float)),
             unit="share", margin="rate", **dog),
        dict(outcome="run-fault rate", frame=ran.assign(y=ran["run_fault"].astype(float)),
             unit="share", margin="rate", **dog),
        dict(outcome="clean heat time", frame=heats_wx.assign(y=heats_wx["clean_time_clean"]),
             unit="s", margin="heat_s", **team),
        dict(outcome="clean-heat rate", frame=heats_wx.assign(y=heats_wx["clean_heat"].astype(float)),
             unit="share", margin="rate", **team),
    ]


# --- Collinearity ----------------------------------------------------------------------

def correlations(heats_wx: pd.DataFrame, weather_day: pd.DataFrame) -> pd.DataFrame:
    """Correlations and variance inflation factors of the weather variables, per heat and per day."""
    day = weather_day.drop_duplicates(["venue", "date"]).rename(columns={
        "temp_mean_c": "temp_c", "humidity_mean_pct": "humidity_pct", "wind_mean_ms": "wind_ms",
        "precip_total_mm": "precip_3h_mm", "precip_24h_before_mm": "precip_24h_mm", "gust_max_ms": "gust_ms"})
    day = day.assign(months=(pd.to_datetime(day["date"]) - SEASON_START).dt.days / 30)
    heat = heats_wx.drop_duplicates("heat_id")
    cols = [*WEATHER_COLUMNS, "months"]
    out = []
    for level, df in (("heat", heat), ("venue-day", day)):
        corr = df[cols].corr()
        x = sm.add_constant(df[cols].astype(float))
        vif = [variance_inflation_factor(x.to_numpy(), i + 1) for i in range(len(cols))]
        out.append(corr.round(3).assign(vif=vif, level=level, n=len(df)).rename_axis("variable").reset_index())
    return pd.concat(out, ignore_index=True)


# --- Within-competition effects ----------------------------------------------------------

def samples(runs_wx: pd.DataFrame, heats_wx: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """The two samples every model is fitted on: all dogs/teams, and WRFT only."""
    return {"field": (runs_wx, heats_wx),
            "WRFT": (runs_wx[runs_wx["is_wrft_dog"]], heats_wx[heats_wx["is_wrft"]])}


def fit_spec(spec: dict, absorb: str | None = None) -> dict:
    """absorbed_ols of one outcome on the weather terms and its controls, clustered on venue-day."""
    return stats.absorbed_ols(spec["frame"], "y", [*TERMS, *spec["controls"]], [absorb or spec["absorb"]],
                              "venue_day", categorical=spec["categorical"], small_sample=True)


def contrast_rows(spec: dict, fit: dict, sample: str, model: str = "within competition") -> pd.DataFrame:
    """One row per coach contrast, in display units, with Holm over the contrasts and a verdict.

    Log run time is turned into % and seconds per run at the sample's median run.
    Clean heat time is in seconds, rates in shares (0.01 = 1 pp).
    """
    median_run = spec["frame"]["run_time"].median() if spec["unit"] == "log" else np.nan
    rows = []
    for label, (factor, weights) in CONTRASTS.items():
        c = stats.linear_combination(fit, weights)
        if spec["unit"] == "log":                       # log effect -> seconds per run
            to_s = lambda b: median_run * (np.exp(b) - 1)
            est, lo, hi, se = to_s(c["estimate"]), to_s(c["ci_low"]), to_s(c["ci_high"]), median_run * c["se"]
            pct = 100 * (np.exp(c["estimate"]) - 1)
        else:
            est, lo, hi, se, pct = c["estimate"], c["ci_low"], c["ci_high"], c["se"], np.nan
        margin = lane.MARGINS[spec["margin"]]
        rows.append({
            "sample": sample, "model": model, "level": spec["level"], "outcome": spec["outcome"],
            "factor": factor, "contrast": label,
            "unit": "s per run" if spec["unit"] == "log" else spec["unit"],
            "estimate": est, "ci_low": lo, "ci_high": hi, "pct": pct,
            "per_heat_s": 4 * est if spec["unit"] == "log" else np.nan,
            "p_value": c["p_value"], "margin": margin,
            "p_tost": stats.tost(est, se, margin, df=fit["t_df"]).item(),
            "rows_used": fit["n"], "groups": fit["n_groups"], "clusters": fit["n_clusters"],
        })
    out = pd.DataFrame(rows)
    out["p_holm"] = stats.holm(out["p_value"])
    out["verdict"] = stats.verdict(out["p_holm"], out["p_tost"])
    return out


def control_rows(spec: dict, fit: dict, sample: str) -> pd.DataFrame:
    """The control terms of a fit, for their own interest (not part of the verdicts)."""
    scale = spec["frame"]["run_time"].median() if spec["unit"] == "log" else 1.0
    tab = fit["table"].set_index("term")
    t = tab.loc[[c for c in spec["controls"] if c in tab.index]]
    return pd.DataFrame({
        "sample": sample, "outcome": spec["outcome"], "control": t.index.map(CONTROL_LABELS),
        "unit": "s per run" if spec["unit"] == "log" else spec["unit"],
        "estimate": scale * t["estimate"].to_numpy(), "ci_low": scale * t["ci_low"].to_numpy(),
        "ci_high": scale * t["ci_high"].to_numpy(), "p_value": t["p_value"].to_numpy(),
    })


def within_competition(runs_wx: pd.DataFrame, heats_wx: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Main model: every outcome, field and WRFT, comparing the same dog (team) within an event.

    Returns the coach contrasts ("effects") and the control terms ("controls").
    """
    effects, controls = [], []
    for sample, (r, h) in samples(runs_wx, heats_wx).items():
        for spec in outcome_specs(r, h):
            fit = fit_spec(spec)
            effects.append(contrast_rows(spec, fit, sample))
            controls.append(control_rows(spec, fit, sample))
    return {"effects": pd.concat(effects, ignore_index=True), "controls": pd.concat(controls, ignore_index=True)}


def within_day(runs_wx: pd.DataFrame, heats_wx: pd.DataFrame) -> pd.DataFrame:
    """Strictest check: the same dog (team) on the same ring-day, so only the diurnal swing is left.

    Rain and wind barely change within a day; the useful rows are temperature
    and humidity.
    """
    parts = []
    for sample, (r, h) in samples(runs_wx, heats_wx).items():
        specs = {s["outcome"]: s for s in outcome_specs(r, h)}
        for outcome, absorb in (("run time", "dog_day"), ("clean heat time", "team_day")):
            parts.append(contrast_rows(specs[outcome], fit_spec(specs[outcome], absorb), sample, "within day"))
    return pd.concat(parts, ignore_index=True)


def wrft_mixed(runs_wx: pd.DataFrame) -> pd.DataFrame:
    """WRFT robustness check: crossed random intercepts for dog and ring-day, events as fixed effects."""
    d = runs_wx[runs_wx["is_wrft_dog"] & runs_wx["valid_speed"]].assign(y=lambda x: np.log(x["run_time"]))
    formula = f"y ~ {' + '.join([*TERMS, *DOG_CONTROLS])} + C(position) + C(competition)"
    fit = stats.crossed_mixed(formula, d, {"dog": "dog_key", "day": "comp_day_id"})
    cov = stats.mixed_fe_cov(fit)
    median_run = d["run_time"].median()
    rows = []
    for label, (factor, weights) in CONTRASTS.items():
        w = pd.Series(weights)
        est = float(w @ fit.fe_params[w.index])
        se = float(np.sqrt(w @ cov.loc[w.index, w.index] @ w))
        rows.append({"sample": "WRFT", "model": "mixed (dog + ring-day random)", "outcome": "run time",
                     "factor": factor, "contrast": label,
                     "estimate": median_run * (np.exp(est) - 1),
                     "ci_low": median_run * (np.exp(est - stats.Z95 * se) - 1),
                     "ci_high": median_run * (np.exp(est + stats.Z95 * se) - 1),
                     "pct": 100 * (np.exp(est) - 1), "p_value": 2 * stats.sps.norm.sf(abs(est / se))})
    return pd.DataFrame(rows)


# --- Between days: weather vs venue and season -------------------------------------------

def day_meta(index_field: pd.DataFrame, weather_day: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """How much of the day-to-day speed differences (4A speed index) weather explains.

    Weighted least squares of the ring-day index (%) on day-mean weather and
    the season (months), weights 1 / SE², errors clustered on venue-day.
    R² is compared for season only, weather only, and both, in sample and
    leaving one event out (each event predicted from the others only).
    """
    wx = weather_day[["comp_day_id", "venue", "temp_mean_c", "humidity_mean_pct", "wind_mean_ms", "rain_hours"]]
    d = index_field.merge(wx, on="comp_day_id", how="left", validate="one_to_one")
    date = pd.to_datetime(d["date"])
    d = d.assign(se=(d["ci_high"] - d["ci_low"]) / (2 * stats.Z95),
                 venue_day=d["venue"] + "|" + date.dt.strftime("%Y-%m-%d"),
                 months=(date - SEASON_START).dt.days / 30,
                 temp10=(d["temp_mean_c"] - HINGE_C) / 10, hum20=(d["humidity_mean_pct"] - 60) / 20,
                 wind3=d["wind_mean_ms"] / 3, wet=d["rain_hours"].gt(0).astype(float))
    specs = {"season only": ["months"], "weather only": ["temp10", "hum20", "wind3", "wet"],
             "weather + season": ["temp10", "hum20", "wind3", "wet", "months"]}
    groups = pd.factorize(d["venue_day"])[0]
    w = 1 / d["se"] ** 2
    fits, coefs = [], []
    for name, cols in specs.items():
        x = sm.add_constant(d[cols])
        fit = sm.WLS(d["pct"], x, weights=w).fit(
            cov_type="cluster", cov_kwds={"groups": groups, "use_correction": True}, use_t=True)
        # Leave one event out: predict each event's days from the other events only.
        loeo = pd.Series(np.nan, index=d.index)
        for event in d["competition"].unique():
            out = d["competition"].eq(event)
            loeo[out] = sm.WLS(d.loc[~out, "pct"], x[~out], weights=w[~out]).fit().predict(x[out])
        fits.append({"model": name, "ring_days": len(d), "venue_days": d["venue_day"].nunique(),
                     "r2": fit.rsquared, "adj_r2": fit.rsquared_adj,
                     "loeo_r2": 1 - (w * (d["pct"] - loeo) ** 2).sum() / (w * (d["pct"] - np.average(d["pct"], weights=w)) ** 2).sum()})
        ci = fit.conf_int()
        coefs.append(pd.DataFrame({"model": name, "term": fit.params.index, "pct": fit.params.to_numpy(),
                                   "ci_low": ci[0].to_numpy(), "ci_high": ci[1].to_numpy(),
                                   "p_value": fit.pvalues.to_numpy()}))
    full = sm.WLS(d["pct"], sm.add_constant(d[specs["weather + season"]]), weights=1 / d["se"] ** 2).fit()
    days = d[["comp_day_id", "competition", "ring", "date", "pct", "ci_low", "ci_high", "temp_mean_c",
              "humidity_mean_pct", "wind_mean_ms", "rain_hours", "months"]]
    days = days.assign(fitted_pct=full.fittedvalues, residual_pct=d["pct"] - full.fittedvalues)
    return {"fit": pd.DataFrame(fits), "coefficients": pd.concat(coefs, ignore_index=True), "days": days}


# --- Shape of the temperature effect -----------------------------------------------------

def dog_adjusted(d: pd.DataFrame) -> pd.Series:
    """Log run time with each dog's own level, its position and the hurdle removed (no day effects).

    What is left is "faster or slower than this dog usually is", which the
    temperature curve and the gradient-boosting check try to explain.
    """
    x = pd.get_dummies(d["position"].astype(str), prefix="pos", drop_first=True, dtype=float)
    x["hurdle_step"] = d["hurdle_step"]
    y = np.log(d["run_time"])
    within = lambda s: s - s.groupby(d["dog_key"]).transform("mean")
    beta = np.linalg.lstsq(x.apply(within).to_numpy(), within(y).to_numpy(), rcond=None)[0]
    resid = y - x.to_numpy() @ beta
    return within(resid)


def temperature_curve(runs_wx: pd.DataFrame, width: float = 2.0) -> pd.DataFrame:
    """Dog-adjusted run time (%) in 2 °C temperature bins, field dogs. Descriptive:
    across venues, so it also carries venue differences."""
    d = runs_wx[runs_wx["valid_speed"] & runs_wx["hurdle_cm"].notna()].copy()
    d["adj_pct"] = 100 * (np.exp(dog_adjusted(d)) - 1)
    d["bin"] = (np.floor(d["temp_c"] / width) * width + width / 2)
    g = d.groupby("bin").agg(runs=("adj_pct", "size"), venue_days=("venue_day", "nunique"),
                             mean_pct=("adj_pct", "mean"), sd=("adj_pct", "std"))
    g["ci_low"] = g["mean_pct"] - stats.Z95 * g["sd"] / np.sqrt(g["runs"])
    g["ci_high"] = g["mean_pct"] + stats.Z95 * g["sd"] / np.sqrt(g["runs"])
    return g.drop(columns="sd").rename_axis("temp_c").reset_index()


# --- Sensitivity ---------------------------------------------------------------------------

SENSITIVITY_OUTCOMES = ["run time", "clean heat time", "false-start rate", "early-pass rate", "clean-heat rate"]


def sensitivity(runs_wx: pd.DataFrame, heats_wx: pd.DataFrame) -> pd.DataFrame:
    """Field sample, within competition, under alternative choices, for the main outcomes.

    "plus hour of day" matters most: within a day, temperature rises with the
    clock, and later heats are also later rounds of the tournament.
    """
    specs = {s["outcome"]: s for s in outcome_specs(runs_wx, heats_wx) if s["outcome"] in SENSITIVITY_OUTCOMES}

    def variant(label, keep=None, extra=(), drop=(), hinge=HINGE_C, temp="temp_c", rain="precip_3h_mm",
                wet_mm=WET_MM, wind=None):
        parts = []
        for spec in specs.values():
            f = spec["frame"] if keep is None else spec["frame"][keep(spec["frame"])]
            if wind is not None:
                f = f.assign(wind_ms=f[wind] / 2)          # gusts are about twice the mean wind
            f = add_terms(f, hinge=hinge, temp=temp, rain=rain, wet_mm=wet_mm)
            controls = [c for c in spec["controls"] if c not in drop] + list(extra)
            spec = {**spec, "frame": f, "controls": controls}
            parts.append(contrast_rows(spec, fit_spec(spec), "field", model=label))
        return pd.concat(parts, ignore_index=True)

    return pd.concat([
        variant("baseline"),
        variant("no fatigue control", drop=("run_no_today", "heat_no_today")),
        variant("no second-day control", drop=("day2",)),
        variant("plus hour of day", extra=("hour",)),
        variant("hinge at 15 °C", hinge=15.0),
        variant("hinge at 25 °C", hinge=25.0),
        variant("apparent temperature", temp="apparent_temp_c"),
        variant("wet ground: >= 1 mm in last 24 h", rain="precip_24h_mm", wet_mm=1.0),
        variant("gusts (/2) instead of mean wind", wind="gust_ms"),
        variant("EFC left out", keep=lambda f: f["competition"].ne("EFC")),
        *[variant(f"leave out: {event}", keep=lambda f, e=event: f["competition"].ne(e))
          for event in sorted(runs_wx["competition"].unique())],
    ], ignore_index=True)


# --- Gradient-boosting check ----------------------------------------------------------------

def _r2(y, pred) -> float:
    y, pred = np.asarray(y), np.asarray(pred)
    return float(1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())


GBM_WEATHER = ["temp_c", "humidity_pct", "wind_ms", "precip_3h_mm"]
GBM_OTHER = ["run_no_today"]     # months and hour extrapolate badly to an unseen event (tried; log 5.x)


def gbm_check(runs_wx: pd.DataFrame, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Can a flexible model predict dog-adjusted run time from the weather on unseen events?

    HistGradientBoosting on the dog-adjusted run time (%), field dogs, from
    the 4 weather variables plus the dog's run number that day (fatigue).
    Leave-one-competition-out cross-validation (11 folds), so the model is
    always scored on an event it has never seen and can't memorise a venue.
    Compares out-of-fold R² with and without the weather features, reports
    held-out permutation importance, and partial dependence for each factor.
    """
    d = runs_wx[runs_wx["valid_speed"] & runs_wx["hurdle_cm"].notna()].copy()
    d["y"] = 100 * (np.exp(dog_adjusted(d)) - 1)
    features = {"weather + fatigue": GBM_WEATHER + GBM_OTHER, "fatigue only": GBM_OTHER}
    make = lambda: HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=3,
                                                 min_samples_leaf=200, random_state=seed)
    groups = d["competition"].to_numpy()
    scores, importance = [], []
    for name, cols in features.items():
        oof = np.full(len(d), np.nan)
        for train, test in LeaveOneGroupOut().split(d, groups=groups):
            model = make().fit(d[cols].iloc[train], d["y"].iloc[train])
            oof[test] = model.predict(d[cols].iloc[test])
            if name == "weather + fatigue":
                imp = permutation_importance(model, d[cols].iloc[test], d["y"].iloc[test], n_repeats=5,
                                             random_state=seed, scoring="neg_mean_squared_error")
                importance.append(pd.DataFrame({"feature": cols, "mse_increase": imp.importances_mean,
                                                "fold": groups[test][0], "rows": len(test)}))
        # Single runs are mostly noise, so the score that matters is per ring-day:
        # does the model, never having seen the event, predict which days run slow?
        day = pd.DataFrame({"y": d["y"], "oof": oof, "g": d["comp_day_id"]}).groupby("g").mean()
        scores.append({"features": name, "runs": len(d), "folds": len(np.unique(groups)),
                       "run_r2": _r2(d["y"], oof), "ring_days": len(day), "day_r2": _r2(day["y"], day["oof"]),
                       "day_corr": float(np.corrcoef(day["y"], day["oof"])[0, 1]),
                       "sd_run_pct": float(d["y"].std()), "sd_day_pct": float(day["y"].std())})
    imp = pd.concat(importance)
    imp = (imp.assign(w=imp["mse_increase"] * imp["rows"]).groupby("feature")
           .apply(lambda g: g["w"].sum() / g["rows"].sum(), include_groups=False)
           .rename("mse_increase").sort_values(ascending=False).reset_index())

    full = make().fit(d[features["weather + fatigue"]], d["y"])
    pdp = []
    for col in GBM_WEATHER:
        res = partial_dependence(full, d[features["weather + fatigue"]], [col], grid_resolution=30,
                                 percentiles=(0.05, 0.95), kind="average")
        pdp.append(pd.DataFrame({"feature": col, "value": res["grid_values"][0],
                                 "pct": res["average"][0] - res["average"][0].mean()}))
    return {"scores": pd.DataFrame(scores), "importance": imp, "pdp": pd.concat(pdp, ignore_index=True)}


# --- Verdict for the coach ------------------------------------------------------------------

SPEED_OUTCOMES = ["run time", "clean heat time"]
RELIABILITY_OUTCOMES = ["false-start rate", "early-pass rate", "run-fault rate", "clean-heat rate"]


def _reading(verdicts: pd.Series) -> str:
    if verdicts.eq("meaningful difference").any():
        return "supported"
    if verdicts.isin(["no effect (equivalent)", "real but negligible"]).all():
        return "refuted (too small to matter)"
    return "inconclusive"


def coach_verdict(effects: pd.DataFrame) -> pd.DataFrame:
    """One line per coach factor: is the hypothesis supported for speed, and for reliability?

    Read on the field sample (about 900 dogs; the physiology is the same for
    WRFT dogs), within competition. Per factor and outcome group:
    *supported* if any contrast is a meaningful difference (Holm-significant,
    not shown inside the margin); *refuted* if every contrast is shown inside
    the margin; otherwise *inconclusive*. WRFT rows that are meaningful are
    listed as a consistency check.
    """
    main = effects[effects["model"].eq("within competition")]
    rows = []
    for factor, g in main.groupby("factor", sort=False):
        field, wrft = g[g["sample"].eq("field")], g[g["sample"].eq("WRFT")]
        run = field[field["outcome"].eq("run time")]
        describe = lambda df: "; ".join(f"{o}, {c}" for o, c in df[["outcome", "contrast"]].itertuples(index=False))
        rows.append({
            "factor": factor,
            "speed": _reading(field.loc[field["outcome"].isin(SPEED_OUTCOMES), "verdict"]),
            "reliability": _reading(field.loc[field["outcome"].isin(RELIABILITY_OUTCOMES), "verdict"]),
            "field_run_effect": "; ".join(f"{c}: {e:+.3f} s/run ({lo:+.3f} to {hi:+.3f})" for c, e, lo, hi in
                                          run[["contrast", "estimate", "ci_low", "ci_high"]].itertuples(index=False)),
            "field_meaningful": describe(field[field["verdict"].eq("meaningful difference")]),
            "wrft_meaningful": describe(wrft[wrft["verdict"].eq("meaningful difference")]),
        })
    return pd.DataFrame(rows)
