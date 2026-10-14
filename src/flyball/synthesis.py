"""Phase 5: synthesis. Every finding ranked in one currency, plus the key numbers.

Impact ledger
-------------
A won heat is the good result (ANALYSIS_LOG.md 2.3), so every lever the
analysis found is converted to the same unit: **expected extra heats won per
season** by WRFT. The engine is the WRFT heat-win model of Phase 3 (logistic
P(win) from the typical speed and start gaps and from who faulted).

A lever is a list of changes to the model inputs of the heats it applies to:

- a *fault change* moves the share of those heats that have a fault (say
  false starts 17 % -> 11 %) by removing faults at random among them, or adding
  them at random to clean heats ("thinning"). Each heat then has a probability
  of carrying each of its own 3 fault types, and P(win) is averaged over the
  8 combinations;
- a *shift* moves the team's typical clean time (`speed_gap`) or start
  (`start_gap`), by a constant or by a per-heat amount (e.g. the heat penalty
  grows with the temperature).

Extra wins = expected wins with the lever - without it, summed over WRFT's
heats and scaled from the model sample to all decided heats. WRFT-vs-WRFT
heats are left out: a club-wide fix can't win the club a heat against itself.
CIs come from DRAWS draws of the model coefficients (cluster-robust
covariance) and, where the size of the lever is itself an estimate (a gap to
peers, the second-day effect, the heat slope), of that size too.

These are what-ifs from an observational model: they rank the levers, they
are not exact promises. Choices are explained in ANALYSIS_LOG.md Step 6.
"""

from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd
from scipy import stats as sps
from scipy.special import expit

from flyball import config, lineup, metrics, stats, weather_effects as we

DRAWS = 2000
SEED = 2023
OWN_FAULTS = ["own_false_start", "own_pass_fault", "own_run_fault"]
FAULT_LABELS = {"own_false_start": "false starts", "own_pass_fault": "early passes",
                "own_run_fault": "run faults"}
PEER_METRIC = {"own_false_start": "false_start_rate", "own_pass_fault": "pass_fault_rate",
               "own_run_fault": "run_fault_rate"}
HEAT_FAULT = {"own_false_start": "any_false_start", "own_pass_fault": "any_pass_fault",
              "own_run_fault": "any_run_fault"}
Z95 = sps.norm.ppf(0.975)


# --- The heats and the model -------------------------------------------------------------

def ledger_frame(t: dict) -> dict:
    """WRFT's decided heats against other clubs, with the fitted heat-win model and its draws.

    Returns the model sample (`d`, one row per heat, plus competition, date,
    day of the event and temperature), the point coefficients, DRAWS
    coefficient draws, and `scale`: all decided external heats / heats in the
    model (the model needs a typical speed on both sides, so a few drop out).
    """
    view = metrics.heat_view(t["heats"])
    model = stats.heat_win_models(metrics.heat_model_frame(view, wrft_focal=True))
    fit = model["fits"]["full"]
    ctx = view[["heat_id", "team_norm", "competition", "date", "opponent_is_wrft", "typ_clean_time"]]
    d = model["data"].merge(ctx, on=["heat_id", "team_norm"], how="left", validate="one_to_one")

    first = t["heats"].groupby("competition")["date"].agg(["min", "max"])
    d["day1_of_two"] = d["date"].eq(d["competition"].map(first["min"])) & first["max"].gt(first["min"]).reindex(
        d["competition"]).to_numpy()
    heat_wx = pd.read_parquet(config.PROCESSED / "heat_weather.parquet")
    d["temp_c"] = d["heat_id"].map(heat_wx.drop_duplicates("heat_id").set_index("heat_id")["temp_c"])

    external = d[~d["opponent_is_wrft"].astype(bool)].reset_index(drop=True)
    h = t["heats"]
    ext = h[h["is_wrft"] & h["outcome"].isin(["win", "loss"]) & ~h["opponent_is_wrft"].astype(bool)]
    rng = np.random.default_rng(SEED)
    draws = rng.multivariate_normal(fit.params.to_numpy(), fit.cov_params().to_numpy(), size=DRAWS)
    return {"d": external, "names": list(fit.params.index), "beta": fit.params.to_numpy()[None, :],
            "draws": draws, "scale": len(ext) / len(external), "n_decided": len(ext),
            "win_rate": ext["outcome"].eq("win").mean(), "fit": fit}


# --- Engine ------------------------------------------------------------------------------

@dataclass
class Change:
    """One change to the model inputs of the heats in `mask`.

    term   : an own-fault column (then `size` is the change in the share of
             heats with that fault, e.g. -0.05) or speed_gap / start_gap
             (then `size` is seconds, times `factor` per heat if given)
    draws  : `size` once per coefficient draw (None: the size is known exactly)
    set_to : True replaces the input instead of changing it: every heat gets
             fault probability `size`, or the team's typical clean time `size`
             (only speed_gap: the opponent's side stays as observed)
    """
    mask: np.ndarray
    term: str
    size: float
    draws: np.ndarray | None = None
    factor: np.ndarray | None = None
    set_to: bool = False


def thin(x: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Probability that each heat has the fault, so that the mean over the heats is `target`.

    x are the observed 0/1 fault flags (m heats); target has one value per
    draw (k). Below the current rate faults are removed at random; above it
    they are added at random to the heats without one. Returns (m, k).
    """
    x = np.asarray(x, float)[:, None]
    current = x.mean()
    target = np.clip(np.asarray(target, float), 0.0, 1.0)[None, :]
    down = x * (target / current if current > 0 else 0.0)
    up = x + (1 - x) * (target - current) / (1 - current) if current < 1 else x
    return np.where(target < current, down, up)


def _inputs(d: pd.DataFrame, changes: list[Change], k: int, use_draws: bool) -> tuple[dict, dict]:
    """Per-heat fault probabilities and shifts, (n, k), for k coefficient draws (k = 1: point)."""
    n = len(d)
    q = {c: np.repeat(d[c].to_numpy(float)[:, None], k, axis=1) for c in OWN_FAULTS}
    shift = {}
    for ch in changes:
        size = np.broadcast_to(ch.draws if use_draws and ch.draws is not None else ch.size, (k,))
        if ch.term in OWN_FAULTS:
            x = d.loc[ch.mask, ch.term].to_numpy(float)
            q[ch.term][ch.mask] = size[None, :] if ch.set_to else thin(x, x.mean() + size)
        else:
            factor = np.ones(int(ch.mask.sum())) if ch.factor is None else np.asarray(ch.factor, float)
            s = shift.setdefault(ch.term, np.zeros((n, k)))
            s[ch.mask] += factor[:, None] * size[None, :]
            if ch.set_to:                                   # own typical clean time -> size
                s[ch.mask] -= d.loc[ch.mask, "typ_clean_time"].to_numpy(float)[:, None]
    return q, shift


def expected_wins(d: pd.DataFrame, names: list[str], beta: np.ndarray, q: dict, shift: dict) -> np.ndarray:
    """Sum over heats of the expected P(win), one value per coefficient row of `beta` (k, p).

    q: own fault -> (n, k) probability the heat has it; shift: term -> (n, k) seconds.
    """
    col = {name: i for i, name in enumerate(names)}
    fixed = [nm for nm in names if nm != "Intercept" and nm not in OWN_FAULTS]
    eta = beta[:, col["Intercept"]][None, :] + d[fixed].to_numpy(float) @ beta[:, [col[f] for f in fixed]].T
    for term, s in shift.items():
        eta = eta + s * beta[:, col[term]][None, :]
    total = np.zeros_like(eta)
    for combo in product((0, 1), repeat=len(OWN_FAULTS)):
        weight = np.ones_like(eta)
        e = eta.copy()
        for c, on in zip(OWN_FAULTS, combo):
            weight *= q[c] if on else 1 - q[c]
            e += on * beta[:, col[c]][None, :]
        total += weight * expit(e)
    return total.sum(axis=0)


def lever_effect(frame: dict, changes: list[Change], reference: list[Change] | None = None) -> dict:
    """Extra wins per season from a lever: point estimate and 95 % interval over the draws.

    The comparison is with the heats as observed, or with `reference` changes
    (e.g. the current line-up, scored by the same model as the new one).
    """
    d, names = frame["d"], frame["names"]
    k = len(frame["draws"])
    reference = reference or []
    base_point = expected_wins(d, names, frame["beta"], *_inputs(d, reference, 1, False))
    base_draws = expected_wins(d, names, frame["draws"], *_inputs(d, reference, k, False))
    point = expected_wins(d, names, frame["beta"], *_inputs(d, changes, 1, False)) - base_point
    draws = expected_wins(d, names, frame["draws"], *_inputs(d, changes, k, True)) - base_draws
    affected = np.zeros(len(d), bool)
    for ch in changes:
        affected |= ch.mask
    s = frame["scale"]
    return _summary(affected.sum() * s, point[0] * s, draws * s)


def _summary(heats: float, point: float, draws: np.ndarray) -> dict:
    return {"heats_affected": heats, "extra_wins": point, "ci_low": np.percentile(draws, 2.5),
            "ci_high": np.percentile(draws, 97.5), "draws": draws}


def _normal_draws(estimate: float, se: float, rng: np.random.Generator) -> np.ndarray:
    return rng.normal(estimate, se, DRAWS)


# --- Levers ---------------------------------------------------------------------------------

def _team_label(team_norm: str) -> str:
    return team_norm.replace("wildrunners ", "").capitalize().replace("Xxl", "XXL")


def fault_gap_levers(frame: dict, t: dict, rng: np.random.Generator) -> list[dict]:
    """Each WRFT team's fault rates down to its division peers (Phase 3 peer benchmark).

    Only gaps where the team is worse than its peers. The gap's own CI is
    drawn too; a draw below zero means "no change" for that draw.
    Returns one lever per team x fault type, one per fault type for all
    teams together, and one for every gap at once.
    """
    d = frame["d"]
    peer = metrics.peer_benchmark(t["heats"]).assign(team_norm=lambda x: x["team"].str.lower())
    peer["se"] = (peer["ci_high"] - peer["ci_low"]) / (2 * Z95)
    single, by_fault = [], {c: [] for c in OWN_FAULTS}
    for p in peer.itertuples(index=False):
        fault = next((c for c, m in PEER_METRIC.items() if m == p.metric), None)
        if fault is None or not p.estimate > 0:
            continue
        mask = d["team_norm"].eq(p.team_norm).to_numpy()
        gap = _normal_draws(p.estimate, p.se, rng)
        ch = Change(mask, fault, -p.estimate, -np.clip(gap, 0, None))
        by_fault[fault].append(ch)
        single.append({"id": f"gap|{_team_label(p.team_norm).lower()}|{fault}",
                       "group": "fault gap to division peers",
                       "lever": f"{_team_label(p.team_norm)}: {FAULT_LABELS[fault]} down to peers "
                                f"({100 * p.estimate:+.1f} pp now)",
                       "changes": [ch], "basis": f"peer_benchmark {p.metric}, Holm p = {p.p_holm:.3f}"})
    totals = [{"id": f"gap_club|{c}", "group": "fault gap to division peers (club)",
               "lever": f"All teams: {FAULT_LABELS[c]} down to peers",
               "changes": chs, "basis": "sum of the team gaps above"} for c, chs in by_fault.items() if chs]
    every = [{"id": "gap_club|all", "group": "fault gap to division peers (club)",
              "lever": "All teams: every fault gap closed",
              "changes": [ch for chs in by_fault.values() for ch in chs], "basis": "all gaps above at once"}]
    return single + totals + every


def fault_probabilities(prof: pd.DataFrame, orders: list[str]) -> pd.DataFrame:
    """P(the heat has a false start / an early pass / a run fault) for named line-ups (dog profiles)."""
    p = prof.set_index("dog")
    rows = []
    for o in orders:
        dogs = o.split(" > ")
        rows.append({"own_false_start": p.at[dogs[0], "false_start_p"],
                     "own_pass_fault": 1 - np.prod(1 - p.loc[dogs[1:], "early_pass_p"].to_numpy()),
                     "own_run_fault": 1 - np.prod(1 - p.loc[dogs, "run_fault_p"].to_numpy())})
    return pd.DataFrame(rows, index=orders)


def line_up_levers(frame: dict, t: dict) -> list[dict]:
    """Each team runs its recommended order (same 4 dogs), or adds the best bench dog.

    Both line-ups are scored by the Phase 4B profiles and put into the win
    model the same way, against the team's actual 2023 opponents: the team's
    typical clean time becomes the line-up's predicted runs, and its fault
    probabilities the line-up's. The new line-up's time also carries the
    change in start and pass time (a second saved anywhere counts the same).
    The current line-up is the reference, so the team's own 2023 line-ups
    don't enter. The opponents are the ones the team met at its last
    competition, where the current line-up raced (earlier opponents were
    matched to other line-ups); the win-rate change on those heats is then
    applied to the team's season volume. Profile values are taken as known
    (no draws): the CIs cover the win model only. A much faster team would
    meet faster opponents (it would be seeded higher), so large gains are
    optimistic.
    """
    d = frame["d"]
    runs, heats = t["runs"], t["heats"]
    cost = lineup.fault_cost(heats)
    prof = lineup.dog_profiles(runs, t["dogs"], t["hurdle_check"])
    recs = lineup.team_recommendations(prof, lineup.current_line_ups(runs), cost)
    out = []
    for r in recs.itertuples(index=False):
        team = d["team_norm"].eq(r.team).to_numpy()
        mask = team & d["competition"].eq(r.competition).to_numpy()
        for kind, new in (("reorder", r.best_order), ("bench swap", r.best_swap_line_up)):
            lever_id = f"lineup_{kind.split()[-1]}|{_team_label(r.team).lower()}"
            orders = [r.current_order, new]
            score = lineup.score_line_ups(prof, orders, cost)
            faults = fault_probabilities(prof, orders)
            runs_now = score["runs_s"].iat[0]
            saved = score["no_fault_s"].iat[0] - score["no_fault_s"].iat[1]

            def arm(runs_s, i):
                return ([Change(mask, "speed_gap", runs_s, set_to=True)]
                        + [Change(mask, c, float(faults[c].iat[i]), set_to=True) for c in OWN_FAULTS])
            gain = score["expected_s"].iat[0] - score["expected_s"].iat[1]
            out.append({"id": lever_id, "group": f"line-up: {kind}",
                        "lever": f"{_team_label(r.team)}: {r.current_order} -> {new}",
                        "changes": arm(runs_now - saved, 1), "reference": arm(runs_now, 0),
                        "extrapolate": team.sum() / mask.sum(),
                        "basis": f"lineup_teams; {gain:.2f} s expected per heat "
                                 f"({saved:.2f} s without faults, P(clean) "
                                 f"{score['p_clean'].iat[0]:.2f} -> {score['p_clean'].iat[1]:.2f})"})
    return out


def day2_fit(t: dict) -> pd.DataFrame:
    """Second day of an event vs the first, same WRFT team at the same event: heat-level fault shares.

    The Phase 4B team model (weather terms, hurdle, heat number, day 2;
    team x event absorbed, clustered on venue-day) with the 3 fault flags
    as outcomes. Gives the size of the "Saturday as clean as Sunday" lever.
    """
    heat_wx = pd.read_parquet(config.PROCESSED / "heat_weather.parquet")
    h = we.heat_frame(t["heats"], heat_wx)
    h = h[h["is_wrft"]]
    rows = []
    for fault, flag in HEAT_FAULT.items():
        spec = dict(frame=h.assign(y=h[flag].astype(float)), controls=we.TEAM_CONTROLS,
                    absorb="team_event", categorical=())
        fit = we.fit_spec(spec)
        row = fit["table"].set_index("term").loc["day2"]
        rows.append({"fault": fault, "estimate": row["estimate"], "se": row["se"],
                     "ci_low": row["ci_low"], "ci_high": row["ci_high"], "p_value": row["p_value"]})
    return pd.DataFrame(rows)


def day2_lever(frame: dict, t: dict, rng: np.random.Generator) -> tuple[list[dict], pd.DataFrame]:
    """Day 1 of two-day events as clean as day 2."""
    d = frame["d"]
    fit = day2_fit(t)
    mask = d["day1_of_two"].to_numpy(bool)
    changes = [Change(mask, f.fault, min(f.estimate, 0.0), np.clip(_normal_draws(f.estimate, f.se, rng), None, 0))
               for f in fit.itertuples(index=False)]
    return [{"id": "day2", "group": "second-day effect", "lever": "Saturday (day 1) as clean as Sunday (day 2)",
             "changes": changes, "basis": "day2 term, heat-level fault flags, WRFT within event"}], fit


def heat_lever(frame: dict, rng: np.random.Generator) -> list[dict]:
    """Upper bound: WRFT keeps full speed above 20 °C while its opponents slow down.

    Heat slows every team (+0.083 s per run per 10 °C above 20 °C, Phase 4B
    field model), so it only changes results if WRFT copes better than its
    opponents. This lever gives WRFT the whole penalty back: 4 runs x slope
    x degrees above 20 / 10, per heat.
    """
    d = frame["d"]
    e = pd.read_csv(config.REPORTS / "phase4b" / "weather_effects.csv")
    row = e[e["sample"].eq("field") & e["outcome"].eq("run time")
            & e["contrast"].eq("temperature +10 °C (above 20 °C)")].iloc[0]
    se = (row["ci_high"] - row["ci_low"]) / (2 * sps.t(int(row["clusters"]) - 1).ppf(0.975))
    hot = d["temp_c"].gt(we.HINGE_C).to_numpy()
    factor = (d.loc[hot, "temp_c"].to_numpy() - we.HINGE_C) / 10
    ch = Change(hot, "speed_gap", -4 * row["estimate"], -4 * _normal_draws(row["estimate"], se, rng), factor)
    return [{"id": "heat", "group": "weather",
             "lever": "Hot days: WRFT keeps its speed above 20 °C, opponents don't (upper bound)",
             "changes": [ch], "basis": f"weather_effects: +{row['estimate']:.3f} s per run per 10 °C above 20 °C"}]


def ceiling_lever(frame: dict) -> list[dict]:
    """No own faults at all: the most any fault work could ever give (a reference, not a target)."""
    d = frame["d"]
    everywhere = np.ones(len(d), bool)
    return [{"id": "ceiling", "group": "reference", "lever": "No own faults at all (ceiling)",
             "changes": [Change(everywhere, c, -d[c].mean()) for c in OWN_FAULTS], "basis": "reference"}]


def impact_ledger(t: dict) -> dict[str, pd.DataFrame]:
    """Every lever in extra heats won per season, ranked. Also returns the day-2 fit it used."""
    frame = ledger_frame(t)
    rng = np.random.default_rng(SEED + 1)
    day2, day2_tab = day2_lever(frame, t, rng)
    levers = (fault_gap_levers(frame, t, rng) + line_up_levers(frame, t) + day2
              + heat_lever(frame, rng) + ceiling_lever(frame))
    rows = []
    for lv in levers:
        eff = lever_effect(frame, lv["changes"], lv.get("reference"))
        x = lv.get("extrapolate", 1.0)                # line-ups: last competition -> season
        eff = {k: v * x for k, v in eff.items()}
        rows.append({"lever_id": lv["id"], "group": lv["group"], "lever": lv["lever"], **eff, "basis": lv["basis"]})
    # The teams' heats don't overlap, so their reorders add up; the draws give the CI of the sum.
    reorders = [r for r in rows if r["lever_id"].startswith("lineup_reorder|")]
    total = _summary(sum(r["heats_affected"] for r in reorders), sum(r["extra_wins"] for r in reorders),
                     np.sum([r["draws"] for r in reorders], axis=0))
    rows.append({"lever_id": "lineup_reorder|all", "group": "line-up: reorder (club)",
                 "lever": "All teams run their recommended order (same dogs)", **total,
                 "basis": "sum of the team reorders"})
    out = pd.DataFrame(rows).drop(columns="draws")
    out["club_win_rate_pp"] = 100 * out["extra_wins"] / frame["n_decided"]
    out["affected_win_rate_pp"] = 100 * out["extra_wins"] / out["heats_affected"]
    out = out.sort_values("extra_wins", ascending=False, ignore_index=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    meta = pd.DataFrame([{"external_decided_heats": frame["n_decided"], "win_rate": frame["win_rate"],
                          "model_heats": len(frame["d"]), "model_win_rate": frame["d"]["win"].mean(),
                          "scale": frame["scale"], "draws": DRAWS, "seed": SEED}])
    return {"impact_ledger": out, "impact_day2_faults": day2_tab, "impact_meta": meta}


# --- Key numbers -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Key:
    """Where one headline number lives: a result table, the row(s), the column.

    `where` selects rows by exact value; `agg` reduces them (else exactly one
    row must match). `ci` names the CI columns, if any.
    """
    key: str
    file: str
    where: dict
    col: str
    unit: str
    log: str
    ci: tuple[str, str] | None = None
    agg: str | None = None


def _k(key, file, where, col, unit, log, ci=None, agg=None) -> Key:
    return Key(key, file, where, col, unit, log, ci, agg)



WRFT, FIELD = "WRFT (all teams)", "Field (non-WRFT)"
TEAMS, ATTRIBUTION, WIN_STATUS, PEERS = (f"phase3/{f}.csv" for f in
                                         ("team_summary", "fault_attribution", "win_by_fault_status", "peer_benchmark"))
LANE, LANE_DAYS, PARTNER = (f"phase4a/{f}.csv" for f in ("lane_run_effect", "lane_by_ring_day", "partner_contrasts"))
EFFECTS, CONTROLS, TOP = "phase4b/weather_effects.csv", "phase4b/weather_controls.csv", "phase4b/lineup_top.csv"
LINEUP_TEAMS, HEIGHT, BACKTEST, STABILITY = (f"phase4b/{f}.csv" for f in
                                             ("lineup_teams", "lineup_height_dog", "lineup_backtest",
                                              "lineup_stability_dogs"))
CI, CI_S = ("ci_low", "ci_high"), ("ci_low_s", "ci_high_s")
DAY2 = "second day of the event"


def _wx(sample: str, contrast: str, outcome: str = "run time") -> dict:
    return {"sample": sample, "outcome": outcome, "contrast": contrast}


def _ctrl(sample: str, outcome: str, control: str = DAY2) -> dict:
    return {"sample": sample, "outcome": outcome, "control": control}


ABOVE_20 = "temperature +10 °C (above 20 °C)"

# Every number findings.md and the deck quote. Units: share (0.158 = 15.8 %), pp, s, pct (%), count, wins.
KEYS = [
    # Phase 3 – the general picture (log Step 2)
    _k("wrft_heats_with_result", TEAMS, {"team": WRFT}, "heats", "count", "2.5"),
    _k("wrft_win_rate", TEAMS, {"team": WRFT}, "win_rate", "share", "2.5", ("win_ci_low", "win_ci_high")),
    _k("field_win_rate", TEAMS, {"team": FIELD}, "win_rate", "share", "2.5"),
    _k("wrft_clean_heat_rate", TEAMS, {"team": WRFT}, "clean_heat_rate", "share", "2.5"),
    _k("field_clean_heat_rate", TEAMS, {"team": FIELD}, "clean_heat_rate", "share", "2.5"),
    _k("wrft_false_start_heats", TEAMS, {"team": WRFT}, "false_start_rate", "share", "2.5"),
    _k("field_false_start_heats", TEAMS, {"team": FIELD}, "false_start_rate", "share", "2.5"),
    _k("wrft_median_pass_s", TEAMS, {"team": WRFT}, "median_pass", "s", "2.5"),
    _k("field_median_pass_s", TEAMS, {"team": FIELD}, "median_pass", "s", "2.5"),
    _k("wrft_median_run_s", TEAMS, {"team": WRFT}, "median_run", "s", "2.5"),
    _k("field_median_run_s", TEAMS, {"team": FIELD}, "median_run", "s", "2.5"),
    _k("wrft_losses", ATTRIBUTION, {"group": WRFT}, "losses", "count", "2.4"),
    _k("wrft_losses_with_fault_share", ATTRIBUTION, {"group": WRFT}, "share_losses_with_fault", "share", "2.4"),
    _k("wrft_avoidable_losses", ATTRIBUTION, {"group": WRFT}, "avoidable_losses", "count", "2.4"),
    _k("wrft_avoidable_share", ATTRIBUTION, {"group": WRFT}, "share_losses_avoidable", "share", "2.4"),
    _k("win_clean_vs_clean", WIN_STATUS, {"own": "own clean", "opp": "opponent clean"}, "win_rate", "share", "2.3", CI),
    _k("win_clean_vs_fault", WIN_STATUS, {"own": "own clean", "opp": "opponent fault"}, "win_rate", "share", "2.3", CI),
    _k("win_fault_vs_clean", WIN_STATUS, {"own": "own fault", "opp": "opponent clean"}, "win_rate", "share", "2.3", CI),
    _k("heat_model_r2_speed", "phase3/heat_win_model_fit.csv", {"model": "speed", "sample": "field"}, "pseudo_r2",
       "r2", "2.3"),
    _k("heat_model_r2_faults", "phase3/heat_win_model_fit.csv", {"model": "faults", "sample": "field"}, "pseudo_r2",
       "r2", "2.3"),
    *(_k(f"rerun_cost_{fault}_s", "phase3/fault_cost.csv", {"fault": fault}, "rerun_seconds_median", "s", "2.4")
      for fault in ("false_start", "pass_fault")),
    _k("xxl_false_start_gap", PEERS, {"team": "WildRunners XXL", "metric": "false_start_rate"}, "estimate", "share",
       "2.5", CI),
    _k("zephyr_run_fault_gap", PEERS, {"team": "WildRunners Zephyr", "metric": "run_fault_rate"}, "estimate", "share",
       "2.5", CI),
    _k("hopefuls_early_pass_gap", PEERS, {"team": "WildRunners hopefuls", "metric": "pass_fault_rate"}, "estimate",
       "share", "2.5", CI),
    *(_k(f"{dog.lower()}_{rate}", "dog_scorecards.csv", {"dog": dog}, rate, "share", "2.7",
         (rate.replace("rate", "ci_low"), rate.replace("rate", "ci_high")))
      for rate, dogs in (("false_start_rate", ("Cookies", "Scotty", "Rex", "Sunny")),
                         ("early_pass_rate", ("Moon", "Bree")), ("run_fault_rate", ("Ted",)))
      for dog in dogs),
    _k("cookies_starts", "dog_scorecards.csv", {"dog": "Cookies"}, "starts", "count", "2.7"),
    *(_k(f"{kind}_fault_rate_{name}", "phase3/pass_window.csv", {"kind": kind, "bin": b}, "fault_rate", "share", "2.6",
         ("fault_ci_low", "fault_ci_high"))
      for kind, name, b in (("start", "0.05_0.08", "(0.05, 0.08]"), ("start", "0.14_0.18", "(0.14, 0.18]"),
                            ("pass", "under_0.08", "(-inf, 0.08]"), ("pass", "0.25_0.35", "(0.25, 0.35]"),
                            ("pass", "over_0.35", "(0.35, inf]"))),
    _k("hurdle_step_s", CONTROLS, _ctrl("field", "run time", "hurdle +2.5 cm"), "estimate", "s", "5.3", CI),
    # Phase 4A – Q1, Q2, Q3 (log Step 4)
    _k("lane_field_s", LANE, {"sample": "field", "model": "within dog-day"}, "seconds", "s", "4.2", CI_S),
    _k("lane_wrft_s", LANE, {"sample": "WRFT", "model": "within dog-day"}, "seconds", "s", "4.2", CI_S),
    _k("lane_ring_day_max_s", LANE_DAYS, {}, "seconds", "s", "4.2", agg="absmax"),
    _k("lane_ring_days", LANE_DAYS, {}, "seconds", "count", "4.2", agg="count"),
    _k("held_pass_intact_male", PARTNER, {"outcome": "held-pass rate (> 1 s)", "level": "intact male",
                                          "spec": "category"}, "estimate", "share", "4.3", CI),
    _k("intact_female_dogs", PARTNER, {"outcome": "held-pass rate (> 1 s)", "level": "intact female",
                                       "spec": "category"}, "incoming_dogs", "count", "4.3"),
    _k("wrft_competition_days", "phase4a/competition_days.csv", {}, "heats", "count", "4.4", agg="count"),
    _k("season_trend_wrft_pct", "phase4a/season_trend.csv", {"sample": "WRFT"}, "pct_per_30_days", "pct", "4.4", CI),
    _k("speed_index_field_min_pct", "phase4a/speed_index.csv", {"sample": "field"}, "pct", "pct", "4.4", agg="min"),
    _k("speed_index_field_max_pct", "phase4a/speed_index.csv", {"sample": "field"}, "pct", "pct", "4.4", agg="max"),
    # Phase 4B – weather and line-up (log Step 5)
    _k("heat_run_s", EFFECTS, _wx("field", ABOVE_20), "estimate", "s", "5.2", CI),
    _k("heat_run_pct", EFFECTS, _wx("field", ABOVE_20), "pct", "pct", "5.2"),
    _k("heat_wrft_run_s", EFFECTS, _wx("WRFT", ABOVE_20), "estimate", "s", "5.2", CI),
    _k("humidity_run_s", EFFECTS, _wx("field", "humidity +20 pp"), "estimate", "s", "5.2", CI),
    _k("wind_run_s", EFFECTS, _wx("field", "wind +3 m/s"), "estimate", "s", "5.2", CI),
    _k("rain_run_s", EFFECTS, _wx("field", "rain in the last 3 h"), "estimate", "s", "5.2", CI),
    _k("weather_day_r2", "phase4b/weather_day_fit.csv", {"model": "weather + season"}, "r2", "r2", "5.5"),
    _k("day2_clean_heat_field", CONTROLS, _ctrl("field", "clean-heat rate"), "estimate", "share", "5.3", CI),
    _k("day2_clean_heat_wrft", CONTROLS, _ctrl("WRFT", "clean-heat rate"), "estimate", "share", "5.3", CI),
    _k("day2_false_start_wrft", CONTROLS, _ctrl("WRFT", "false-start rate"), "estimate", "share", "5.3", CI),
    _k("day2_run_time_field_s", CONTROLS, _ctrl("field", "run time"), "estimate", "s", "5.3", CI),
    _k("fatigue_run_s", CONTROLS, _ctrl("field", "run time", "each earlier run that day (dog)"), "estimate", "s",
       "5.3", CI),
    _k("a_team", TOP, {"rank": 1}, "line_up", "text", "5.8"),
    _k("a_team_expected_s", TOP, {"rank": 1}, "expected_s", "s", "5.8"),
    _k("a_team_no_fault_s", TOP, {"rank": 1}, "no_fault_s", "s", "5.8"),
    _k("a_team_runs_s", TOP, {"rank": 1}, "runs_s", "s", "5.8"),
    _k("a_team_p_clean", TOP, {"rank": 1}, "p_clean", "share", "5.8"),
    _k("lineup_orders_searched", "phase4b/lineup_meta.csv", {}, "orders", "count", "5.8", agg="max"),
    _k("fault_cost_s", "phase4b/lineup_meta.csv", {}, "fault_cost_s", "s", "5.8", agg="max"),
    _k("hopefuls_order_gain_s", LINEUP_TEAMS, {"team": "wildrunners hopefuls"}, "gain_from_order_s", "s", "5.9"),
    _k("zephyr_order_gain_s", LINEUP_TEAMS, {"team": "wildrunners zephyr"}, "gain_from_order_s", "s", "5.9"),
    _k("xxl_order_gain_s", LINEUP_TEAMS, {"team": "wildrunners xxl"}, "gain_from_order_s", "s", "5.9"),
    _k("easy_height_dog_net_s", HEIGHT, {"height_dog": "Easy"}, "gain_vs_without_s", "s", "5.9"),
    _k("gordon_height_dog_net_s", HEIGHT, {"height_dog": "Gordon"}, "gain_vs_without_s", "s", "5.9"),
    _k("backtest_spearman", BACKTEST, {"check": "clean time: model"}, "spearman", "r", "5.10"),
    _k("backtest_auc_clean", BACKTEST, {"check": "clean heat: model P(clean)"}, "auc", "auc", "5.10"),
    *(_k(f"stability_{dog.lower()}", STABILITY, {"dog": dog}, "share_of_resamples", "share", "5.10")
      for dog in ("Enola", "Alfie", "Maggie", "Pax")),
]
LEDGER_KEYS = {          # key -> lever_id in impact_ledger.csv (extra heats won per season)
    "impact_ceiling": "ceiling",
    "impact_day2": "day2",
    "impact_all_fault_gaps": "gap_club|all",
    "impact_false_start_gaps": "gap_club|own_false_start",
    "impact_early_pass_gaps": "gap_club|own_pass_fault",
    "impact_run_fault_gaps": "gap_club|own_run_fault",
    "impact_xxl_false_starts": "gap|xxl|own_false_start",
    "impact_zephyr_run_faults": "gap|zephyr|own_run_fault",
    "impact_hopefuls_reorder": "lineup_reorder|hopefuls",
    "impact_zephyr_reorder": "lineup_reorder|zephyr",
    "impact_xxl_reorder": "lineup_reorder|xxl",
    "impact_maximini_reorder": "lineup_reorder|maximini",
    "impact_all_reorders": "lineup_reorder|all",
    "impact_zephyr_swap": "lineup_swap|zephyr",
    "impact_hopefuls_swap": "lineup_swap|hopefuls",
    "impact_heat": "heat",
}
KEYS += [_k(key, "phase5/impact_ledger.csv", {"lever_id": lid}, "extra_wins", "wins", "6.1", CI)
         for key, lid in LEDGER_KEYS.items()]
KEYS += [_k("wrft_heats_vs_clubs", "phase5/impact_meta.csv", {}, "external_decided_heats", "count", "6.1", agg="max"),
         _k("wrft_win_rate_vs_clubs", "phase5/impact_meta.csv", {}, "win_rate", "share", "6.1", agg="max")]


def _resolve(k: Key, tables: dict[str, pd.DataFrame]) -> dict:
    """The value (and CI) of one key, from its table."""
    df = tables.setdefault(k.file, pd.read_csv(config.REPORTS / k.file))
    rows = df
    for col, value in k.where.items():
        rows = rows[rows[col].eq(value)]
    if k.agg is None:
        if len(rows) != 1:
            raise ValueError(f"{k.key}: {len(rows)} rows match {k.where} in {k.file}")
        value = rows[k.col].iat[0]
        ci = [rows[c].iat[0] for c in k.ci] if k.ci else None
    else:
        values = rows[k.col]
        value = {"min": values.min, "max": values.max, "count": values.size,
                 "absmax": lambda: values.abs().max()}[k.agg]
        value = value() if callable(value) else value
        ci = None
    out = {"value": value.item() if hasattr(value, "item") else value, "unit": k.unit,
           "source": f"reports/{k.file}", "log_step": k.log}
    if ci is not None:
        out["ci"] = [float(c) for c in ci]
    return out


def key_numbers() -> dict[str, dict]:
    """Every headline number with its unit, CI, source table and log step (reads reports/)."""
    tables: dict[str, pd.DataFrame] = {}
    return {k.key: _resolve(k, tables) for k in KEYS}
