"""Q2: does it matter whether a dog passes onto an intact or neutered male or female?

The unit is one WRFT pass: the outgoing dog (positions 2-4) crosses the line
as the incoming dog returns. The question is about the incoming dog's
category, so the outcomes are those of the outgoing dog: its racing pass
time, held-pass rate, tight-pass (`ok`) share, early-pass rate and run time.
Choices are explained in ANALYSIS_LOG.md Step 4:

- Both dogs get a random intercept (crossed random effects). The category of
  the incoming dog is a between-dog trait, so its CI must reflect how many
  incoming dogs carry it (intact female: 2 dogs), not how many passes.
- Intact dogs in the team are young (median about 2 years, neutered dogs
  about 6), so a "category" effect can be an age or experience effect. The
  `adjusted` specification adds both dogs' ages and the team.
- A pass slower than 1 s (metrics.HELD_PASS_S) was held back on purpose.
  Those few passes dominated the mean pass time, so pass time is measured
  on racing passes and holding back is its own outcome (held-pass rate).
- Rates are linear-probability models (0.01 = 1 percentage point); a
  logistic GEE is a sensitivity check.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from flyball import metrics, stats

CATEGORIES = ["neutered male", "neutered female", "intact male", "intact female"]   # first = reference
PAIRS = ["neutered->neutered", "neutered->intact", "intact->neutered", "intact->intact"]  # incoming->outgoing
RANDOM = {"dog": "dog_key", "partner": "prev_dog_key"}
YOUNG_MONTHS = 18

# outcome column: (label, unit, equivalence margin in outcome units)
OUTCOMES = {
    "pass_s": ("pass time (racing passes, <= 1 s)", "s", 0.02),
    "held": ("held-pass rate (> 1 s)", "share", 0.02),
    "ok": ("tight-pass (ok) share", "share", 0.02),
    "early": ("early-pass rate", "share", 0.02),
    "log_rt": ("run time of the outgoing dog", "s", 0.05),
}
CONTROLS = "C(position) + hurdle_step + C(comp_day_id)"
SPECS = {
    "category": f"C(incoming) + C(own) + {CONTROLS}",
    "category, adjusted for age and team": f"C(incoming) + C(own) + incoming_age_y + own_age_y + C(team_norm) + {CONTROLS}",
}


def _split_category(cat: pd.Series) -> tuple[pd.Series, pd.Series]:
    """'neutered female' -> ('female', 'neutered')."""
    parts = cat.str.split(" ", expand=True)
    return parts[1], parts[0]


def pass_frame(runs: pd.DataFrame, ok_value: float = metrics.OK_PASS_IMPUTE) -> pd.DataFrame:
    """One row per WRFT pass attempt whose incoming dog is a known WRFT dog.

    Adds the incoming dog's age and its run time in the same heat, the
    outcome columns (pass_s for racing passes with `ok` = ok_value, held,
    ok, early, log_rt; pass_all_s keeps the held passes) and
    categorical columns with neutered male as the reference level.
    """
    w = runs[runs["is_wrft_dog"] & runs["position"].ge(2) & runs["pass_code"].ne("missing")
             & runs["prev_category"].notna()].copy()
    incoming = (runs[["row_id", "position", "age_months", "run_time", "valid_speed"]]
                .assign(position=lambda x: x["position"] + 1)
                .rename(columns={"age_months": "incoming_age_months", "run_time": "incoming_run_time",
                                 "valid_speed": "incoming_valid_speed"}))
    w = w.merge(incoming, on=["row_id", "position"], how="left", validate="one_to_one")

    cats = pd.CategoricalDtype(CATEGORIES)
    w["incoming"] = w["prev_category"].astype(cats)
    w["own"] = w["category"].astype(cats)
    w["incoming_sex"], w["incoming_status"] = _split_category(w["prev_category"])
    w["own_sex"], w["own_status"] = _split_category(w["category"])
    w["pair"] = (w["incoming_status"] + "->" + w["own_status"]).astype(pd.CategoricalDtype(PAIRS))
    w["incoming_age_y"] = w["incoming_age_months"] / 12
    w["own_age_y"] = w["age_months"] / 12
    w["hurdle_step"] = (w["hurdle_cm"] - 25.0) / 2.5

    w["pass_all_s"] = w["pass_time"].where(w["valid_pass"]).mask(w["pass_code"].eq("ok"), ok_value)
    w["held"] = w["pass_all_s"].gt(metrics.HELD_PASS_S).astype(float).where(w["pass_all_s"].notna())
    w["pass_s"] = w["pass_all_s"].where(w["held"].eq(0))
    w["ok"] = w["pass_code"].eq("ok").astype(float)
    w["early"] = w["pass_fault"].astype(float)
    w["log_rt"] = np.log(w["run_time"].where(w["valid_speed"]))
    return w.reset_index(drop=True)


# --- Descriptives ------------------------------------------------------------------------

def partner_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Per incoming-dog category: sample sizes, ages, raw pass and run profile."""
    g = frame.groupby("incoming", observed=True)
    timed = frame[frame["valid_pass"]]
    out = pd.DataFrame({
        "passes": g.size(),
        "incoming_dogs": g["prev_dog_key"].nunique(),
        "outgoing_dogs": g["dog_key"].nunique(),
        "incoming_age_median_y": g["incoming_age_y"].median(),
        # Medians count `ok` as 0, the smallest value (metrics module convention).
        "median_pass_s": timed["pass_time"].mask(timed["pass_code"].eq("ok"), 0.0)
                         .groupby(timed["incoming"], observed=True).median(),
        "held_pass_rate": g["held"].mean(),
        "ok_share": g["ok"].mean(),
        "early_passes": g["early"].sum().astype(int),
        "early_pass_rate": g["early"].mean(),
        "outgoing_median_run_s": frame["run_time"].where(frame["valid_speed"])
                                 .groupby(frame["incoming"], observed=True).median(),
    })
    out["early_ci_low"], out["early_ci_high"] = stats.wilson_ci(out["early_passes"], out["passes"])
    return out.rename_axis("incoming_category").reset_index()


# --- Models --------------------------------------------------------------------------------

def fit_terms(frame: pd.DataFrame, outcome: str, rhs: str, prefix: str) -> tuple[pd.DataFrame, dict]:
    """Crossed mixed model `outcome ~ rhs`; the terms starting with `prefix`, plus their joint test.

    Rows missing the outcome or either dog's age are dropped first, so every
    specification of an outcome uses the same passes. Run time is modelled
    on the log scale and reported in seconds at the median run.
    """
    d = frame.dropna(subset=[outcome, "incoming_age_y", "own_age_y"])
    d = d.assign(incoming=d["incoming"].cat.remove_unused_categories(),     # a dropped level would
                 own=d["own"].cat.remove_unused_categories())               # leave an all-zero column
    fit = stats.crossed_mixed(f"{outcome} ~ {rhs}", d, RANDOM)
    names = [n for n in fit.fe_params.index if n.startswith(prefix)]
    tab = stats.mixed_table(fit, names)
    joint = stats.wald_joint(fit.fe_params, stats.mixed_fe_cov(fit), names)
    scale = d["run_time"].median() if outcome == "log_rt" else 1.0
    tab[["estimate", "se", "ci_low", "ci_high"]] *= scale
    label, unit, margin = OUTCOMES[outcome]
    tab.insert(0, "outcome", label)
    tab["unit"] = unit
    tab["level"] = tab["term"].str.extract(r"\[T\.(.+)\]$", expand=False)
    tab["p_tost"] = stats.tost(tab["estimate"], tab["se"], margin)
    tab["passes"] = len(d)
    return tab, {"outcome": label, "passes": len(d), **joint}


def partner_models(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Main question: incoming-dog category, without and with the age/team adjustment.

    `contrasts`: each category against an incoming neutered male, per outcome
    and specification, with 95 % CI, TOST and verdict (Holm within outcome x spec).
    `joint`: "does the incoming category matter at all?" per outcome and
    specification, Holm over the 4 outcomes of a specification.
    """
    contrasts, joints = [], []
    for spec, rhs in SPECS.items():
        for outcome in OUTCOMES:
            tab, joint = fit_terms(frame, outcome, rhs, "C(incoming)")
            tab["p_holm"] = stats.holm(tab["p_value"])
            contrasts.append(tab.assign(spec=spec))
            joints.append({"spec": spec, **joint})
    contrasts = pd.concat(contrasts, ignore_index=True)
    contrasts["verdict"] = stats.verdict(contrasts["p_holm"], contrasts["p_tost"])
    contrasts["incoming_dogs"] = contrasts["level"].map(frame.groupby("prev_category")["prev_dog_key"].nunique())
    joint = pd.DataFrame(joints)
    joint["p_holm"] = joint.groupby("spec")["p_value"].transform(stats.holm)
    return {"contrasts": contrasts, "joint": joint}


INTERACTIONS = {   # name: (right-hand side, prefix of the interaction terms)
    "sex x sex": (f"C(incoming_sex) * C(own_sex) + C(incoming_status) + C(own_status) + {CONTROLS}",
                  "C(incoming_sex)[T.male]:C(own_sex)"),
    "neutered x neutered": (f"C(incoming_status) * C(own_status) + C(incoming_sex) + C(own_sex) + {CONTROLS}",
                            "C(incoming_status)[T.neutered]:C(own_status)"),
    # The same 2 x 2 as four cells against neutered->neutered: easier to read than an interaction term.
    "neutered/intact pairing cells": (f"C(pair) + C(incoming_sex) + C(own_sex) + {CONTROLS}", "C(pair)"),
}


def partner_interactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Does the pairing matter (e.g. male onto male), beyond each dog's own category?"""
    rows = []
    for name, (rhs, prefix) in INTERACTIONS.items():
        for outcome in OUTCOMES:
            tab, joint = fit_terms(frame, outcome, rhs, prefix)
            rows.append(tab.assign(interaction=name, joint_p=joint["p_value"]))
    out = pd.concat(rows, ignore_index=True)
    out["p_holm"] = out.groupby("interaction")["p_value"].transform(stats.holm)
    return out


def partner_sensitivity(runs: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Does the answer survive other reasonable choices? One row per variant x outcome x term."""
    base = SPECS["category"]
    young = (frame["incoming_age_months"] < YOUNG_MONTHS) | (frame["age_months"] < YOUNG_MONTHS)
    variants = [  # name, frame, outcomes, rhs, term prefix
        ("merged: sex only", frame, OUTCOMES, f"C(incoming_sex) + C(own_sex) + {CONTROLS}", "C(incoming_sex)"),
        ("merged: neutered only", frame, OUTCOMES, f"C(incoming_status) + C(own_status) + {CONTROLS}",
         "C(incoming_status)"),
        ("intact females left out", frame[frame["prev_category"].ne("intact female")], OUTCOMES, base, "C(incoming)"),
        ("dogs under 18 months left out", frame[~young], OUTCOMES, base, "C(incoming)"),
        ("pass time with held passes included", frame.assign(pass_s=frame["pass_all_s"]),
         ["pass_s"], base, "C(incoming)"),
        ("ok pass counted as 0 s", pass_frame(runs, ok_value=0.0), ["pass_s"], base, "C(incoming)"),
        ("ok pass counted as 0.08 s", pass_frame(runs, ok_value=0.08), ["pass_s"], base, "C(incoming)"),
    ]
    rows = []
    for name, d, outcomes, rhs, prefix in variants:
        for outcome in outcomes:
            tab, joint = fit_terms(d, outcome, rhs, prefix)
            rows.append(tab.assign(variant=name, scale="difference", joint_p=joint["p_value"]))
    rows.append(_gee_odds_ratios(frame))
    return pd.concat(rows, ignore_index=True)


def _gee_odds_ratios(frame: pd.DataFrame) -> pd.DataFrame:
    """Logistic GEE (exchangeable within outgoing dog) for the two rates, as odds ratios."""
    rows = []
    for outcome in ("ok", "early"):
        d = frame.dropna(subset=[outcome])
        fit = smf.gee(f"{outcome} ~ C(incoming) + C(own) + {CONTROLS}", groups="dog_key", data=d,
                      family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
        names = [n for n in fit.params.index if n.startswith("C(incoming)")]
        tab = stats.coef_table(fit, exp=True).set_index("term").loc[names].reset_index()
        joint = stats.wald_joint(fit.params, fit.cov_params(), names)
        rows.append(tab.assign(outcome=OUTCOMES[outcome][0], variant="logistic GEE (odds ratio)",
                               scale="odds ratio", joint_p=joint["p_value"], passes=len(d),
                               level=tab["term"].str.extract(r"\[T\.(.+)\]$", expand=False)))
    return pd.concat(rows, ignore_index=True)
