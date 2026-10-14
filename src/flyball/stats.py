"""Statistical helpers: confidence intervals, shrinkage, multiple-test
correction, equivalence tests and the model wrappers used in Phases 3 and 4.

Conventions (plan.md, "Statistical standards"):
- repeated measures: dogs are random effects, or standard errors are
  cluster-robust on the unit that repeats (race, team, dog);
- effect sizes with 95 % CIs, not just p-values;
- Holm correction within a family of tests (BH for screens over many units);
- "no effect" claims are backed by an equivalence test (TOST).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import optimize, stats as sps
from statsmodels.stats.multitest import multipletests

Z95 = sps.norm.ppf(0.975)


# --- Rates ----------------------------------------------------------------------

def wilson_ci(k, n, z: float = Z95) -> tuple[np.ndarray, np.ndarray]:
    """Wilson score interval for k successes out of n (vectorised; NaN where n = 0)."""
    k, n = np.asarray(k, dtype=float), np.asarray(n, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return np.clip(centre - half, 0, 1), np.clip(centre + half, 0, 1)


def eb_shrink_rate(k, n) -> np.ndarray:
    """Empirical-Bayes rate: k/n pulled towards the group mean, more so when n is small.

    A beta prior Beta(a, b) is fitted to the group by maximum likelihood
    (beta-binomial), and each unit gets its posterior mean (k + a) / (n + a + b).
    A dog with 0 faults in 5 runs then no longer ranks as "perfect".
    Units with n = 0 get NaN.
    """
    k, n = np.asarray(k, dtype=float), np.asarray(n, dtype=float)
    has = n > 0

    def neg_loglik(log_ab):
        a, b = np.exp(log_ab)
        return -sps.betabinom.logpmf(k[has], n[has], a, b).sum()

    mean = k[has].sum() / n[has].sum()
    start = np.log([mean * 10, (1 - mean) * 10])
    a, b = np.exp(optimize.minimize(neg_loglik, start, method="Nelder-Mead").x)
    return np.where(has, (k + a) / (n + a + b), np.nan)


def eb_shrink_mean(values: pd.Series, groups: pd.Series) -> pd.DataFrame:
    """Empirical-Bayes group means: each group's mean pulled towards the overall mean.

    One-way random-effects estimate: the between-group variance tau² is the
    variance of the group means minus their average sampling variance, and a
    group with n values keeps the share n / (n + sigma²/tau²) of its own mean.
    A dog with 3 starts then can't rank as the best starter on luck.
    Returns n, raw mean and shrunken mean per group.
    """
    d = pd.DataFrame({"v": values, "g": groups}).dropna()
    g = d.groupby("g")["v"].agg(["size", "mean", "var"]).rename(columns={"size": "n"})
    sigma2 = d["v"].sub(d.groupby("g")["v"].transform("mean")).pow(2).sum() / max(len(d) - len(g), 1)
    grand = d["v"].mean()
    tau2 = max(g["mean"].var() - (sigma2 / g["n"]).mean(), 1e-12)
    weight = g["n"] / (g["n"] + sigma2 / tau2)
    return pd.DataFrame({"n": g["n"], "raw_mean": g["mean"],
                         "shrunk_mean": grand + weight * (g["mean"] - grand)})


def holm(pvalues) -> np.ndarray:
    """Holm-adjusted p-values (NaN-safe)."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    if ok.any():
        out[ok] = multipletests(p[ok], method="holm")[1]
    return out


def bh(pvalues) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (NaN-safe), for screens over many units."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    if ok.any():
        out[ok] = multipletests(p[ok], method="fdr_bh")[1]
    return out


def auc(y, score) -> float:
    """Area under the ROC curve via the Mann-Whitney rank formula."""
    y, score = np.asarray(y), np.asarray(score)
    ranks = sps.rankdata(score)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def coef_table(fit, exp: bool = False, scale: float = 1.0) -> pd.DataFrame:
    """Tidy table of estimates with 95 % CIs; `exp` for odds ratios / ratios."""
    ci = fit.conf_int()
    out = pd.DataFrame({
        "term": fit.params.index,
        "estimate": fit.params.to_numpy(),
        "ci_low": ci.iloc[:, 0].to_numpy(),
        "ci_high": ci.iloc[:, 1].to_numpy(),
        "p_value": fit.pvalues.to_numpy(),
    })
    if exp:
        out[["estimate", "ci_low", "ci_high"]] = np.exp(out[["estimate", "ci_low", "ci_high"]])
    elif scale != 1.0:
        out[["estimate", "ci_low", "ci_high"]] *= scale
    return out


# --- Equivalence and verdicts -----------------------------------------------------

def tost(estimate, se, margin, df: float | None = None) -> np.ndarray:
    """Two one-sided tests: p-value for "|effect| < margin".

    A small p (< 0.05) means the effect is shown to lie inside ±margin, i.e.
    practically equivalent to zero. Same as the 90 % CI lying inside ±margin.
    Normal approximation by default; with `df`, a t distribution (few clusters).
    """
    est, se = np.asarray(estimate, dtype=float), np.asarray(se, dtype=float)
    dist = sps.norm if df is None else sps.t(df)
    p_low = dist.sf((est + margin) / se)      # H0: effect <= -margin
    p_high = dist.cdf((est - margin) / se)    # H0: effect >= +margin
    return np.maximum(p_low, p_high)


def verdict(p_value, p_tost, alpha: float = 0.05) -> np.ndarray:
    """Plain-language reading of a difference test plus an equivalence test."""
    sig = np.asarray(p_value, dtype=float) < alpha
    equiv = np.asarray(p_tost, dtype=float) < alpha
    return np.select([sig & equiv, sig, equiv],
                     ["real but negligible", "meaningful difference", "no effect (equivalent)"],
                     default="inconclusive")


def wald_joint(params: pd.Series, cov: pd.DataFrame, names: list[str]) -> dict:
    """Joint Wald test that all `names` coefficients are zero."""
    b = params[names].to_numpy()
    v = cov.loc[names, names].to_numpy()
    chi2 = float(b @ np.linalg.solve(v, b))
    return {"chi2": chi2, "df": len(names), "p_value": float(sps.chi2.sf(chi2, len(names)))}


def wald_equal(params: pd.Series, cov: pd.DataFrame, names: list[str]) -> dict:
    """Joint Wald test that all `names` coefficients are equal to each other."""
    k = len(names)
    r = np.hstack([-np.ones((k - 1, 1)), np.eye(k - 1)])     # b_i - b_0 = 0 for i > 0
    b = r @ params[names].to_numpy()
    v = r @ cov.loc[names, names].to_numpy() @ r.T
    chi2 = float(b @ np.linalg.solve(v, b))
    return {"chi2": chi2, "df": k - 1, "p_value": float(sps.chi2.sf(chi2, k - 1))}


# --- Model wrappers --------------------------------------------------------------------

def speed_frame(runs: pd.DataFrame) -> pd.DataFrame:
    """Valid-speed runs of known dogs, with log run time and the hurdle in 2.5 cm steps."""
    d = runs[runs["valid_speed"] & runs["dog_key"].notna() & runs["hurdle_cm"].notna()].copy()
    d["log_rt"] = np.log(d["run_time"])
    d["hurdle_step"] = (d["hurdle_cm"] - 25.0) / 2.5
    return d


def absorbed_ols(df: pd.DataFrame, outcome: str, terms: list[str], absorb: list[str], cluster: str,
                 categorical: tuple[str, ...] = (), small_sample: bool = False) -> dict:
    """OLS with one set of fixed effects removed by demeaning, errors clustered.

    Every variable is demeaned within the `absorb` groups (e.g. dog x day),
    so each coefficient compares rows of the same group only: "the same dog
    on the same day, once in the red lane and once in the blue". This gives
    the same estimates as adding a dummy per group, but stays fast with
    thousands of groups. Groups with a single row carry no information and
    are dropped. `categorical` columns become 0/1 dummies (first level is the
    reference). Standard errors are clustered on `cluster` and corrected for
    the degrees of freedom the absorbed groups use up.

    With few clusters (e.g. 22 venue-days), `small_sample=True` uses a t
    distribution with G - 1 degrees of freedom for CIs and p-values instead
    of the normal; `t_df` in the result says which was used.
    """
    d = df.dropna(subset=[outcome, *terms, *categorical, *absorb, cluster])
    d = d[d.groupby(absorb)[outcome].transform("size") > 1]
    X = d[terms].astype(float)
    if categorical:
        X = X.join(pd.get_dummies(d[list(categorical)].astype(str), drop_first=True, dtype=float))
    data = X.assign(**{outcome: d[outcome].astype(float)})
    demeaned = data - data.groupby([d[a] for a in absorb]).transform("mean")
    X = demeaned[X.columns]
    X = X.loc[:, X.abs().max() > 1e-12]                  # drop columns with no within-group variation
    fit = sm.OLS(demeaned[outcome], X).fit(cov_type="cluster",
                                           cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    n, k = len(d), X.shape[1]
    n_fe = d.groupby(absorb).ngroups
    corr = np.sqrt((n - k) / (n - k - n_fe))
    cov = fit.cov_params() * corr**2
    se = np.sqrt(np.diag(cov))
    z = fit.params.to_numpy() / se
    n_clusters = d[cluster].nunique()
    t_df = n_clusters - 1 if small_sample else None
    dist = sps.norm if t_df is None else sps.t(t_df)
    crit = dist.ppf(0.975)
    table = pd.DataFrame({
        "term": X.columns, "estimate": fit.params.to_numpy(), "se": se,
        "ci_low": fit.params.to_numpy() - crit * se, "ci_high": fit.params.to_numpy() + crit * se,
        "p_value": 2 * dist.sf(np.abs(z)),
    })
    return {"table": table, "params": fit.params, "cov": cov, "n": n, "n_groups": n_fe,
            "n_clusters": n_clusters, "t_df": t_df}


def linear_combination(fit: dict, weights: dict[str, float]) -> dict:
    """Estimate, SE, 95 % CI and p-value of sum(weight x coefficient) from an absorbed_ols fit.

    Example: {"temp10": 1, "hot10": 1} is the slope above a temperature hinge.
    Terms missing from the fit (no within-group variation) count as 0.
    """
    names = [t for t in weights if t in fit["params"].index]
    w = np.array([weights[t] for t in names])
    est = float(w @ fit["params"][names].to_numpy())
    se = float(np.sqrt(w @ fit["cov"].loc[names, names].to_numpy() @ w))
    dist = sps.norm if fit["t_df"] is None else sps.t(fit["t_df"])
    crit = dist.ppf(0.975)
    return {"estimate": est, "se": se, "ci_low": est - crit * se, "ci_high": est + crit * se,
            "p_value": float(2 * dist.sf(abs(est / se)))}


def crossed_mixed(formula: str, data: pd.DataFrame, random: dict[str, str], reml: bool = True):
    """Linear mixed model with crossed random intercepts, one per entry of `random`.

    Example: random={"dog": "dog_key", "partner": "prev_dog_key"} gives every
    outgoing dog and every incoming dog its own intercept. A trait carried by
    few dogs (e.g. 2 intact females) then gets a CI that reflects the number
    of dogs, not just the number of passes.
    """
    vc = {name: f"0 + C({col})" for name, col in random.items()}
    return smf.mixedlm(formula, data.assign(_one=1), groups="_one", vc_formula=vc).fit(reml=reml)


def mixed_table(fit, names: list[str] | None = None) -> pd.DataFrame:
    """Fixed-effect estimates of a MixedLM fit with 95 % CIs (all or selected terms)."""
    params, se = fit.fe_params, fit.bse_fe
    if names is not None:
        params, se = params[names], se[names]
    return pd.DataFrame({
        "term": params.index, "estimate": params.to_numpy(), "se": se.to_numpy(),
        "ci_low": (params - Z95 * se).to_numpy(), "ci_high": (params + Z95 * se).to_numpy(),
        "p_value": 2 * sps.norm.sf(np.abs(params / se).to_numpy()),
    })


def mixed_fe_cov(fit) -> pd.DataFrame:
    """Covariance matrix of the fixed effects of a MixedLM fit."""
    names = fit.fe_params.index
    return fit.cov_params().loc[names, names]


# --- Within-division comparison of one team against its peers ----------------------

def within_division_gap(df: pd.DataFrame, outcome: str, focal: pd.Series,
                        strata: str = "comp_div", cluster: str = "team_norm") -> dict:
    """Difference between the focal team and the other teams of the same divisions.

    OLS of `outcome ~ focal + C(strata)` on the divisions the focal team raced
    in, with standard errors clustered on team (heats of one team are not
    independent). For a 0/1 outcome this is a linear probability model, so
    the estimate reads directly as percentage points.
    """
    d = df.assign(focal=focal.astype(int))
    d = d[d[strata].isin(d.loc[d["focal"].eq(1), strata])].dropna(subset=[outcome])
    if d["focal"].nunique() < 2 or d[cluster].nunique() < 3:
        return {"estimate": np.nan, "ci_low": np.nan, "ci_high": np.nan, "p_value": np.nan, "n": len(d)}
    fit = smf.ols(f"{outcome} ~ focal + C({strata})", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    lo, hi = fit.conf_int().loc["focal"]
    return {"estimate": fit.params["focal"], "ci_low": lo, "ci_high": hi,
            "p_value": fit.pvalues["focal"], "n": len(d)}


# --- Heat-win model ---------------------------------------------------------------

FAULT_TERMS = ["own_false_start", "own_pass_fault", "own_run_fault",
               "opp_false_start", "opp_pass_fault", "opp_run_fault"]
SPEED_TERMS = ["speed_gap", "start_gap"]


def heat_win_models(model_df: pd.DataFrame, cluster: str = "race_id") -> dict:
    """Logistic models of P(focal team wins the heat).

    Three nested specifications answer "speed or clean running?":
      speed  : the teams' typical (pre-heat) speed and start gaps only
      faults : who faulted in this heat only
      full   : both
    Standard errors are clustered on race (heats of one race share teams,
    dogs and conditions). Returns the fits plus a comparison table with
    McFadden's pseudo-R² and AUC for each specification.
    """
    specs = {"speed": SPEED_TERMS, "faults": FAULT_TERMS, "full": SPEED_TERMS + FAULT_TERMS}
    d = model_df.dropna(subset=["win", *SPEED_TERMS]).copy()
    groups = pd.factorize(d[cluster])[0]
    null = sm.Logit(d["win"], np.ones(len(d))).fit(disp=0)
    fits, rows = {}, []
    for name, terms in specs.items():
        fit = smf.logit(f"win ~ {' + '.join(terms)}", data=d).fit(
            disp=0, cov_type="cluster", cov_kwds={"groups": groups})
        fits[name] = fit
        rows.append({"model": name, "n_heats": int(fit.nobs),
                     "pseudo_r2": 1 - fit.llf / null.llf,
                     "auc": auc(d["win"], fit.predict(d))})
    return {"fits": fits, "comparison": pd.DataFrame(rows), "data": d}


# --- Dog run-time model -------------------------------------------------------------

DOG_RUN_FORMULA = "log_rt ~ C(position) + hurdle_step + C(comp_day_id)"


def dog_run_model(runs: pd.DataFrame) -> dict:
    """Within-dog effects of running position and hurdle height on run time.

    Mixed model  log(run_time) ~ C(position) + hurdle_step + C(comp_day_id) + (1 | dog)
    on valid-speed runs. hurdle_step = (hurdle - 25 cm) / 2.5, so its
    coefficient is the change per hurdle step. Competition-day fixed effects
    absorb venue, surface and weather, so the effects compare a dog with
    itself on the same day. On the log scale, 100 * coefficient ≈ % change.

    A dog fixed-effects OLS with dog-clustered errors is fitted as a
    robustness check of the same terms.
    """
    d = speed_frame(runs)
    mixed = smf.mixedlm(DOG_RUN_FORMULA, d, groups=d["dog_key"]).fit(reml=True)
    fe = smf.ols(DOG_RUN_FORMULA + " + C(dog_key)", d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["dog_key"])[0]})

    terms = ["C(position)[T.2]", "C(position)[T.3]", "C(position)[T.4]", "hurdle_step"]
    base = d["run_time"].median()
    rows = []
    for label, fit in (("mixed", mixed), ("dog_fixed_effects", fe)):
        ci = fit.conf_int()
        for t in terms:
            est, lo, hi = fit.params[t], *ci.loc[t]
            rows.append({"model": label, "term": t,
                         "pct": 100 * (np.exp(est) - 1),
                         "pct_low": 100 * (np.exp(lo) - 1), "pct_high": 100 * (np.exp(hi) - 1),
                         "seconds_at_median": base * (np.exp(est) - 1),
                         "p_value": fit.pvalues[t]})
    effects = pd.DataFrame(rows)
    effects.attrs.update(n_runs=len(d), n_dogs=d["dog_key"].nunique(), median_run=base)

    # Shrunken dog speed: the dog's random effect at position 1, 25 cm, average day.
    day_fx = [v for k, v in mixed.fe_params.items() if k.startswith("C(comp_day_id)")]
    typical = mixed.fe_params["Intercept"] + np.mean([0.0, *day_fx])
    re = pd.Series({dog: v.iloc[0] for dog, v in mixed.random_effects.items()})
    adjusted = np.exp(typical + re).rename("adj_run_s")
    return {"effects": effects, "adjusted_speed": adjusted, "mixed": mixed, "fixed": fe}
