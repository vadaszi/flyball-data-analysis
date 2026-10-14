"""Phase 4B (4e): the ideal WRFT line-up.

A heat takes start + 4 runs + 3 passes, and any fault costs a rerun. So a
line-up is scored by its *expected heat time*:

    E[T] = start(d1) + sum_i run(d_i, h_min, position i) + sum_{i>=2} pass(d_i)
           + fault cost x expected number of faults

where h_min is the hurdle set by the smallest dog. Every 4-dog set and all
24 running orders are scored, so the search is exhaustive, not heuristic.
Choices are explained in ANALYSIS_LOG.md Step 5:

- dog speed comes from a mixed model with a random intercept *and* a random
  hurdle slope per dog, so a dog seen at one height borrows the team's slope;
  a dog's total slope is floored at 0 (a higher hurdle never makes it faster);
- start and pass times are shrunken means (stats.eb_shrink_mean), fault rates
  empirical-Bayes rates (stats.eb_shrink_rate), so a dog with few attempts
  can't rank first on luck;
- only dogs with MIN_STARTS starts may run first: starting is a specialist skill;
- a dog's height is the hurdle it typically set as the smallest dog in 2023
  (wrft_hurdle_check), or the master jump height if it rarely set it.
"""

from itertools import combinations, permutations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from flyball import metrics, stats

POOL_MIN_RUNS = 20          # user decision (2026-10-13): every WRFT dog with >= 20 valid runs
MIN_STARTS = 10             # a dog needs this many starts to be trusted as the first dog
MIN_HEIGHT_ROWS = 3         # a raced height counts once a dog set the hurdle this often
HEIGHTS = np.arange(15.0, 32.6, 2.5)
ORDERS = np.array(list(permutations(range(4))))     # 24 running orders
BACKTEST_SPLIT = "2023-09-01"                       # profiles from Apr-Jul, test on Sep-Oct


# --- Dog profiles ----------------------------------------------------------------------

def speed_model(runs: pd.DataFrame) -> dict:
    """Run time of each WRFT dog at any hurdle and position, on an average competition day.

    MixedLM  log(run_time) ~ C(position) + hurdle_step + C(comp_day_id)
             + (1 + hurdle_step | dog)
    Returns the fixed parts and each dog's intercept and (floored) total slope.
    """
    d = stats.speed_frame(runs[runs["is_wrft_dog"]])
    fit = smf.mixedlm(stats.DOG_RUN_FORMULA, d, groups=d["dog_key"], re_formula="~hurdle_step").fit(reml=True)
    fe = fit.fe_params
    day_fx = [v for k, v in fe.items() if k.startswith("C(comp_day_id)")]
    re = pd.DataFrame(fit.random_effects).T.rename(columns={"Group": "u0", "hurdle_step": "u1"})
    slope = (fe["hurdle_step"] + re["u1"]).rename("slope")
    return {
        "base": fe["Intercept"] + np.mean([0.0, *day_fx]),          # average day
        "position": np.array([0.0, *(fe[f"C(position)[T.{p}]"] for p in (2, 3, 4))]),
        "u0": re["u0"], "slope": slope.clip(lower=0.0), "n_floored": int(slope.lt(0).sum()),
    }


def predict_run(model: dict, dogs, hurdle_cm, position) -> np.ndarray:
    """Predicted run time (s) for dogs at the given hurdle (cm) and position (1-4), vectorised."""
    dogs = pd.Index(dogs)
    step = (np.asarray(hurdle_cm, dtype=float) - 25.0) / 2.5
    pos = model["position"][np.asarray(position) - 1]
    log_rt = (model["base"] + pos + model["u0"].reindex(dogs).to_numpy()
              + model["slope"].reindex(dogs).to_numpy() * step)
    return np.exp(log_rt)


def raced_height(hurdle_check: pd.DataFrame, dogs: pd.DataFrame) -> pd.Series:
    """Each dog's height for the line-up: typical hurdle when it set it, else its master jump height."""
    master = dogs.set_index("dog")["jump_height_cm"]
    hc = hurdle_check.set_index("dog")
    raced = hc.loc[hc["n_rows_as_height_dog"] >= MIN_HEIGHT_ROWS, "typical_hurdle_cm"]
    return raced.reindex(master.index).fillna(master).rename("height_cm")


def dog_profiles(runs: pd.DataFrame, dogs: pd.DataFrame, hurdle_check: pd.DataFrame) -> pd.DataFrame:
    """One row per WRFT dog: speed, start, pass, fault rates, height, and whether it is in the pool."""
    w = runs[runs["is_wrft_dog"]]
    model = speed_model(runs)
    starts = w[w["position"].eq(1) & w["pass_code"].ne("missing")]
    passes = w[w["position"].ge(2) & w["pass_code"].ne("missing")]
    ran = w[w["run_code"].ne("missing")]

    def racing_time(df):          # start/pass time of fault-free attempts; held ones (> 1 s) left out
        t = metrics.ok_imputed(df["pass_time"], df["pass_code"], df["valid_pass"])
        return t.where(t <= metrics.HELD_PASS_S)

    start_t = stats.eb_shrink_mean(racing_time(starts), starts["dog_key"])
    pass_t = stats.eb_shrink_mean(racing_time(passes), passes["dog_key"])

    def rate(df, flag):
        g = df.groupby("dog_key")[flag].agg(["sum", "size"])
        return pd.Series(stats.eb_shrink_rate(g["sum"], g["size"]), index=g.index), g["size"], g["sum"].sum() / g["size"].sum()

    fs, n_starts, fs_all = rate(starts, "pass_fault")
    ep, n_passes, ep_all = rate(passes, "pass_fault")
    rf, _, rf_all = rate(ran, "run_fault")

    prof = pd.DataFrame(index=pd.Index(sorted(w["dog_key"].dropna().unique()), name="dog"))
    prof["valid_runs"] = w[w["valid_speed"]].groupby("dog_key").size().reindex(prof.index).fillna(0).astype(int)
    prof["height_cm"] = raced_height(hurdle_check, dogs).reindex(prof.index)
    prof["run_25cm_s"] = predict_run(model, prof.index, 25.0, 2)
    prof["run_at_own_height_s"] = predict_run(model, prof.index, prof["height_cm"], 2)
    prof["slope_s_per_step"] = prof["run_25cm_s"] * model["slope"].reindex(prof.index)
    prof["starts"] = n_starts.reindex(prof.index).fillna(0).astype(int)
    prof["start_s"] = start_t["shrunk_mean"].reindex(prof.index).fillna(start_t["raw_mean"].mean())
    prof["false_start_p"] = fs.reindex(prof.index).fillna(fs_all)
    prof["passes"] = n_passes.reindex(prof.index).fillna(0).astype(int)
    prof["pass_s"] = pass_t["shrunk_mean"].reindex(prof.index).fillna(pass_t["raw_mean"].mean())
    prof["early_pass_p"] = ep.reindex(prof.index).fillna(ep_all)
    prof["run_fault_p"] = rf.reindex(prof.index).fillna(rf_all)
    prof["can_start"] = prof["starts"] >= MIN_STARTS
    prof["in_pool"] = prof["valid_runs"] >= POOL_MIN_RUNS
    # The speed terms travel with the profile: per-dog columns plus scalar attrs.
    # (Only scalars in attrs: pandas copies and compares attrs on every operation.)
    prof["speed_u0"] = model["u0"].reindex(prof.index)
    prof["speed_slope"] = model["slope"].reindex(prof.index)
    prof.attrs.update(speed_base=float(model["base"]), speed_position=tuple(model["position"]),
                      n_slopes_floored=model["n_floored"])
    return prof.reset_index()


def profile_model(prof: pd.DataFrame) -> dict:
    """The speed model stored in a profile table, in the form predict_run takes."""
    return {"base": prof.attrs["speed_base"], "position": np.array(prof.attrs["speed_position"]),
            "u0": prof.set_index("dog")["speed_u0"], "slope": prof.set_index("dog")["speed_slope"]}


def fault_cost(heats: pd.DataFrame) -> float:
    """Seconds a corrected fault adds to the heat: median rerun time over corrected faults (Phase 3)."""
    cost = metrics.fault_cost_seconds(heats)
    c = cost[cost["corrected_n"] > 0]
    return float(np.average(c["rerun_seconds_median"], weights=c["corrected_n"]))


# --- Scoring and search ------------------------------------------------------------------

def _arrays(prof: pd.DataFrame) -> dict:
    """Profile columns as arrays, plus each dog's predicted run at every hurdle height and position."""
    model = profile_model(prof)
    dogs = prof["dog"].to_numpy()
    h, p = np.meshgrid(HEIGHTS, np.arange(1, 5), indexing="ij")
    run = np.stack([predict_run(model, [d] * h.size, h.ravel(), p.ravel()).reshape(h.shape) for d in dogs])
    start = np.where(prof["can_start"], prof["start_s"], np.inf)
    return {"dogs": dogs, "run": run, "start": start, "pass": prof["pass_s"].to_numpy(),
            "fs": prof["false_start_p"].to_numpy(), "ep": prof["early_pass_p"].to_numpy(),
            "rf": prof["run_fault_p"].to_numpy(),
            "h_idx": np.searchsorted(HEIGHTS, prof["height_cm"].to_numpy())}


def score_orders(a: dict, ordered: np.ndarray, cost: float) -> dict[str, np.ndarray]:
    """Expected heat time and its parts for an (n, 4) array of dog indices in running order."""
    h = a["h_idx"][ordered].min(axis=1)                       # the smallest dog sets the hurdle
    runs = a["run"][ordered, h[:, None], np.arange(4)].sum(axis=1)
    start = a["start"][ordered[:, 0]]
    passes = a["pass"][ordered[:, 1:]].sum(axis=1)
    n_faults = a["fs"][ordered[:, 0]] + a["ep"][ordered[:, 1:]].sum(axis=1) + a["rf"][ordered].sum(axis=1)
    p_clean = ((1 - a["fs"][ordered[:, 0]]) * (1 - a["ep"][ordered[:, 1:]]).prod(axis=1)
               * (1 - a["rf"][ordered]).prod(axis=1))
    clean_time = start + runs + passes
    return {"expected_s": clean_time + cost * n_faults, "no_fault_s": clean_time, "start_s": start,
            "runs_s": runs, "passes_s": passes, "fault_s": cost * n_faults, "p_clean": p_clean,
            "hurdle_cm": HEIGHTS[h]}


def best_orders(a: dict, sets: np.ndarray, cost: float) -> tuple[np.ndarray, np.ndarray]:
    """For each 4-dog set (rows of `sets`), the running order with the lowest expected time."""
    best_t = np.full(len(sets), np.inf)
    best_o = np.zeros_like(sets)
    for order in ORDERS:
        ordered = sets[:, order]
        t = score_orders(a, ordered, cost)["expected_s"]
        better = t < best_t
        best_t[better], best_o[better] = t[better], ordered[better]
    return best_o, best_t


def search(prof: pd.DataFrame, cost: float, top: int = 50) -> pd.DataFrame:
    """Every 4-dog set from the pool, in its best order; the `top` line-ups by expected heat time."""
    a = _arrays(prof)
    pool = np.flatnonzero(prof["in_pool"].to_numpy())
    sets = np.array(list(combinations(pool, 4)))
    ordered, t = best_orders(a, sets, cost)
    keep = np.argsort(t)[:top]
    out = _describe(a, ordered[keep], cost)
    out.attrs.update(n_sets=len(sets), n_orders=len(sets) * len(ORDERS), pool=len(pool))
    return out


def _describe(a: dict, ordered: np.ndarray, cost: float) -> pd.DataFrame:
    """Readable table of ordered line-ups with their scores."""
    s = score_orders(a, ordered, cost)
    names = a["dogs"][ordered]
    out = pd.DataFrame({f"dog{i + 1}": names[:, i] for i in range(4)})
    out["line_up"] = [" > ".join(row) for row in names]
    for k, v in s.items():
        out[k] = v
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    return out


def dog_frequency(top: pd.DataFrame) -> pd.DataFrame:
    """How often each dog appears among the top line-ups, and in which positions."""
    long = top.melt(id_vars="rank", value_vars=["dog1", "dog2", "dog3", "dog4"], var_name="position", value_name="dog")
    out = long.groupby("dog").agg(appearances=("rank", "size"), best_rank=("rank", "min"),
                                  usual_position=("position", lambda s: s.mode().iat[0]))
    return out.sort_values(["appearances", "best_rank"], ascending=[False, True]).reset_index()


# --- Recommendations ------------------------------------------------------------------------

def _index(prof: pd.DataFrame, names) -> np.ndarray:
    pos = pd.Series(np.arange(len(prof)), index=prof["dog"])
    return pos.loc[list(names)].to_numpy()


def reserves(prof: pd.DataFrame, best: pd.Series, cost: float, n: int = 2) -> pd.DataFrame:
    """The pool dogs that cost least when swapped in for one of the A-team (best order each time)."""
    a = _arrays(prof)
    team = _index(prof, best[["dog1", "dog2", "dog3", "dog4"]])
    others = [i for i in np.flatnonzero(prof["in_pool"]) if i not in team]
    rows = []
    for r in others:
        sets = np.array([np.where(np.arange(4) == k, r, team) for k in range(4)])
        ordered, t = best_orders(a, sets, cost)
        k = int(np.argmin(t))
        rows.append({"reserve": a["dogs"][r], "replaces": a["dogs"][team[k]],
                     "line_up": " > ".join(a["dogs"][ordered[k]]), "expected_s": t[k],
                     "cost_vs_a_team_s": t[k] - best["expected_s"]})
    return pd.DataFrame(rows).sort_values("cost_vs_a_team_s", ignore_index=True).head(n)


def current_line_ups(runs: pd.DataFrame) -> pd.DataFrame:
    """Each WRFT team's most-used line-up (set and order) at its last competition."""
    w = runs[runs["is_wrft"] & runs["is_wrft_dog"]]
    wide = w.pivot_table(index=["row_id", "team_norm", "date", "competition"], columns="position",
                         values="dog_key", aggfunc="first").dropna().reset_index()
    wide = wide[wide[[1, 2, 3, 4]].nunique(axis=1).eq(4)]
    last_comp = wide.sort_values("date").groupby("team_norm")["competition"].last()
    last = wide[wide["competition"].eq(wide["team_norm"].map(last_comp))]
    last = last.assign(order=last[[1, 2, 3, 4]].agg(" > ".join, axis=1),
                       dog_set=last[[1, 2, 3, 4]].apply(lambda r: "|".join(sorted(r)), axis=1))
    rows = []
    for team, g in last.groupby("team_norm"):
        dog_set = g["dog_set"].mode().iat[0]
        same = g[g["dog_set"].eq(dog_set)]
        rows.append({"team": team, "competition": g["competition"].iat[0], "date": g["date"].max(),
                     "heats_with_set": len(same), "order": same["order"].mode().iat[0]})
    return pd.DataFrame(rows)


def team_recommendations(prof: pd.DataFrame, current: pd.DataFrame, cost: float) -> pd.DataFrame:
    """For each current line-up: its expected time, the best order of the same 4 dogs, the best swap.

    Swaps only bring in *bench* dogs: pool dogs that are in no team's current
    line-up, so one team's advice never takes a dog from another team.
    """
    a = _arrays(prof)
    used = {d for o in current["order"] for d in o.split(" > ")}
    bench = [i for i in np.flatnonzero(prof["in_pool"]) if a["dogs"][i] not in used]
    rows = []
    for c in current.itertuples(index=False):
        names = c.order.split(" > ")
        if not set(names) <= set(prof["dog"]):
            continue
        actual = _index(prof, names)[None, :]
        now = score_orders(a, actual, cost)
        reordered, t_re = best_orders(a, np.sort(actual, axis=1), cost)
        swaps = np.array([np.where(np.arange(4) == k, r, actual[0]) for r in bench for k in range(4)])
        sw_order, sw_t = best_orders(a, swaps, cost)
        incoming = np.repeat([a["dogs"][r] for r in bench], 4)
        options = (pd.DataFrame({"dog": incoming, "t": sw_t, "k": np.arange(len(sw_t))})
                   .sort_values("t").drop_duplicates("dog").head(3))
        k = int(options["k"].iat[0])
        out_dog = (set(names) - set(a["dogs"][sw_order[k]])).pop()
        rows.append({
            "team": c.team, "competition": c.competition, "date": c.date, "current_order": c.order,
            "current_expected_s": now["expected_s"][0], "current_p_clean": now["p_clean"][0],
            "hurdle_cm": now["hurdle_cm"][0],
            "best_order": " > ".join(a["dogs"][reordered[0]]), "best_order_expected_s": t_re[0],
            "gain_from_order_s": now["expected_s"][0] - t_re[0],
            "best_bench_swap": f"{out_dog} -> {options['dog'].iat[0]}",
            "best_swap_line_up": " > ".join(a["dogs"][sw_order[k]]), "best_swap_expected_s": sw_t[k],
            "gain_from_swap_s": now["expected_s"][0] - sw_t[k],
            "bench_options": ", ".join(f"{d} ({now['expected_s'][0] - t:+.2f} s)"
                                       for d, t in zip(options["dog"], options["t"])),
        })
    return pd.DataFrame(rows)


def height_dog(prof: pd.DataFrame, cost: float, max_height: float = 22.5) -> pd.DataFrame:
    """Does a small "height dog" pay? Best line-up with each small pool dog vs the best without one.

    `hurdle_saving_s` is what the 3 partners gain from the lower hurdle;
    `own_cost_s` is how much slower the small dog itself is than the 4th dog
    of the best line-up without a small dog. The difference decides.
    """
    a = _arrays(prof)
    pool = np.flatnonzero(prof["in_pool"])
    small = [i for i in pool if prof["height_cm"].iat[i] <= max_height]
    sets = np.array(list(combinations(pool, 4)))
    has_small = np.isin(sets, small).any(axis=1)
    ordered, t = best_orders(a, sets, cost)
    j = int(np.argmin(np.where(has_small, np.inf, t)))
    base = _describe(a, ordered[[j]], cost).iloc[0]
    rows = []
    for s in small:
        with_s = np.isin(sets, [s]).any(axis=1)
        i = int(np.argmin(np.where(with_s, t, np.inf)))
        best = _describe(a, ordered[[i]], cost).iloc[0]
        partners = [d for d in ordered[i] if d != s]
        positions = [int(np.flatnonzero(ordered[i] == d)[0]) for d in partners]
        h_with = np.searchsorted(HEIGHTS, best["hurdle_cm"])
        h_without = a["h_idx"][partners].min()
        saving = sum(a["run"][d, h_without, p] - a["run"][d, h_with, p] for d, p in zip(partners, positions))
        rows.append({"height_dog": a["dogs"][s], "height_cm": prof["height_cm"].iat[s],
                     "run_at_own_height_s": prof["run_at_own_height_s"].iat[s],
                     "best_line_up_with_it": best["line_up"], "hurdle_cm": best["hurdle_cm"],
                     "expected_s": best["expected_s"], "hurdle_saving_s": saving,
                     "best_without_small_dog": base["line_up"], "without_expected_s": base["expected_s"],
                     "gain_vs_without_s": base["expected_s"] - best["expected_s"]})
    return pd.DataFrame(rows).sort_values("expected_s", ignore_index=True)


def score_line_ups(prof: pd.DataFrame, orders: list[str], cost: float) -> pd.DataFrame:
    """Scores of named line-ups ("Maggie > Enola > Pax > Alfie"), one row each, in the given order."""
    ordered = np.stack([_index(prof, o.split(" > ")) for o in orders])
    return _describe(_arrays(prof), ordered, cost).drop(columns="rank")


def comparison(prof: pd.DataFrame, best: pd.Series, recs: pd.DataFrame, cost: float) -> pd.DataFrame:
    """The A-team, then each current team's line-up and its best order: the rows of the breakdown chart."""
    labels, orders = ["A-team: " + best["line_up"]], [best["line_up"]]
    for r in recs.itertuples(index=False):
        name = r.team.replace("wildrunners ", "").capitalize().replace("Xxl", "XXL")
        labels += [f"{name} now: {r.current_order}", f"{name} reordered: {r.best_order}"]
        orders += [r.current_order, r.best_order]
    out = score_line_ups(prof, orders, cost)
    out.insert(0, "label", labels)
    return out


# --- Backtest and stability -------------------------------------------------------------------

def backtest(runs: pd.DataFrame, heats: pd.DataFrame, dogs: pd.DataFrame,
             hurdle_check: pd.DataFrame, split: str = BACKTEST_SPLIT) -> dict[str, pd.DataFrame]:
    """Fit profiles on Apr-Jul only and predict the Sep-Oct WRFT heats.

    - clean time: sum of the 4 predicted runs at the heat's actual hurdle and
      positions, for clean heats whose 4 dogs were profiled; compared with a
      naive baseline (sum of each dog's raw training median run);
    - clean-heat probability: predicted P(clean) vs what happened, Brier
      score against the training clean-heat rate as a constant forecast;
    - errors by hurdle height: the baseline already holds each dog's usual
      height, so the model can only add value where the height is unusual.
    """
    date = pd.to_datetime(runs["date"])
    train, test = runs[date < split], runs[date >= split]
    prof = dog_profiles(train, dogs, hurdle_check)
    model = profile_model(prof)
    prof = prof.set_index("dog")
    raw_median = train[train["valid_speed"] & train["is_wrft_dog"]].groupby("dog_key")["run_time"].median()

    w = test[test["is_wrft"] & test["is_wrft_dog"]]
    wide = w.pivot_table(index="row_id", columns="position", values="dog_key", aggfunc="first")
    wide = wide.dropna()
    known = wide.isin(prof.index).all(axis=1)
    h = heats.set_index("row_id").loc[wide.index]
    test_rows = h[h["is_wrft"] & h["win_value"].notna()].index
    wide, known = wide.loc[test_rows], known.loc[test_rows]
    rows = []
    for row_id, names in wide[known].iterrows():
        hr = h.loc[row_id]
        dogs4 = names[[1, 2, 3, 4]].to_list()
        pred = predict_run(model, dogs4, [hr["hurdle_cm"]] * 4, [1, 2, 3, 4]).sum()
        p_clean = ((1 - prof.at[dogs4[0], "false_start_p"]) * np.prod(1 - prof.loc[dogs4[1:], "early_pass_p"])
                   * np.prod(1 - prof.loc[dogs4, "run_fault_p"]))
        rows.append({"row_id": row_id, "date": hr["date"], "competition": hr["competition"], "team": hr["team_norm"],
                     "line_up": " > ".join(dogs4), "hurdle_cm": hr["hurdle_cm"],
                     "clean_heat": bool(hr["clean_heat"]),
                     "actual_clean_time": hr["clean_time"] if hr["clean_heat"] else np.nan,
                     "predicted_clean_time": pred, "baseline_clean_time": raw_median.reindex(dogs4).sum(),
                     "predicted_p_clean": p_clean})
    heats_out = pd.DataFrame(rows)

    c = heats_out.dropna(subset=["actual_clean_time"])
    train_heats = heats[heats["is_wrft"] & heats["win_value"].notna() & (pd.to_datetime(heats["date"]) < split)]
    base_rate = train_heats["clean_heat"].mean()
    y = heats_out["clean_heat"].astype(float)
    summary = pd.DataFrame([
        {"check": "clean time: model", "n": len(c), "mae_s": (c["predicted_clean_time"] - c["actual_clean_time"]).abs().mean(),
         "bias_s": (c["predicted_clean_time"] - c["actual_clean_time"]).mean(),
         "spearman": c["predicted_clean_time"].corr(c["actual_clean_time"], method="spearman")},
        {"check": "clean time: baseline (sum of raw medians)", "n": len(c),
         "mae_s": (c["baseline_clean_time"] - c["actual_clean_time"]).abs().mean(),
         "bias_s": (c["baseline_clean_time"] - c["actual_clean_time"]).mean(),
         "spearman": c["baseline_clean_time"].corr(c["actual_clean_time"], method="spearman")},
        {"check": "clean heat: model P(clean)", "n": len(heats_out),
         "brier": ((heats_out["predicted_p_clean"] - y) ** 2).mean(), "auc": stats.auc(y, heats_out["predicted_p_clean"]),
         "mean_predicted": heats_out["predicted_p_clean"].mean(), "observed": y.mean()},
        {"check": "clean heat: baseline (training rate)", "n": len(heats_out),
         "brier": ((base_rate - y) ** 2).mean(), "mean_predicted": base_rate, "observed": y.mean()},
    ])
    summary.attrs.update(test_heats=len(wide), unprofiled=int((~known).sum()),
                         unprofiled_dogs=sorted(set(wide[~known].stack()) - set(prof.index)))
    err = c.assign(model=c["predicted_clean_time"] - c["actual_clean_time"],
                   baseline=c["baseline_clean_time"] - c["actual_clean_time"])
    by_hurdle = err.groupby("hurdle_cm").agg(heats=("model", "size"), model_bias_s=("model", "mean"),
                                             baseline_bias_s=("baseline", "mean"),
                                             model_mae_s=("model", lambda e: e.abs().mean()),
                                             baseline_mae_s=("baseline", lambda e: e.abs().mean())).reset_index()
    calib = (heats_out.assign(bin=pd.qcut(heats_out["predicted_p_clean"], 5, duplicates="drop"))
             .groupby("bin", observed=True).agg(heats=("clean_heat", "size"), predicted=("predicted_p_clean", "mean"),
                                                observed=("clean_heat", "mean")).reset_index(drop=True))
    return {"summary": summary, "heats": heats_out, "by_hurdle": by_hurdle, "calibration": calib}


def stability(runs: pd.DataFrame, dogs: pd.DataFrame, hurdle_check: pd.DataFrame, cost: float,
              reps: int = 50, seed: int = 0, top: int = 5) -> dict[str, pd.DataFrame]:
    """Resample WRFT competition days with replacement, refit the profiles and search again.

    Returns how often each dog is in the best line-up, and how often the
    full-data A-team stays among the top `top` line-ups of a resample.
    """
    rng = np.random.default_rng(seed)
    w = runs[runs["is_wrft_dog"]]
    days = w["comp_day_id"].unique()
    in_best, a_team_top = [], []
    full = search(dog_profiles(runs, dogs, hurdle_check), cost, top=1).iloc[0]
    a_team = {full["dog1"], full["dog2"], full["dog3"], full["dog4"]}
    for rep in range(reps):
        draw = rng.choice(days, size=len(days), replace=True)
        boot = pd.concat([w[w["comp_day_id"].eq(d)].assign(comp_day_id=f"{d}#{k}") for k, d in enumerate(draw)],
                         ignore_index=True)
        prof = dog_profiles(boot, dogs, hurdle_check)
        res = search(prof, cost, top=top)
        in_best.extend(res.loc[0, ["dog1", "dog2", "dog3", "dog4"]].to_list())
        a_team_top.append(any({r.dog1, r.dog2, r.dog3, r.dog4} == a_team for r in res.itertuples()))
    freq = (pd.Series(in_best).value_counts().rename_axis("dog").rename("share_of_resamples") / reps).reset_index()
    summary = pd.DataFrame([{"reps": reps, "a_team": " | ".join(sorted(a_team)),
                             f"a_team_in_top_{top}": float(np.mean(a_team_top))}])
    return {"dogs": freq, "summary": summary}
