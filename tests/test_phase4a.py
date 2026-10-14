"""Phase 4A: the new statistical helpers on synthetic data, plus invariants of Q1-Q3 on the real data."""

import warnings

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from flyball import competition, config, lane, metrics, partner, stats


# --- Helpers on synthetic inputs ---------------------------------------------------------

def test_tost_and_verdict():
    # Estimate 0 with a tight CI: shown to be inside ±0.05. Estimate on the margin: not shown (p = 0.5).
    p = stats.tost([0.0, 0.05, -0.05], [0.01, 0.01, 0.01], 0.05)
    assert p[0] < 1e-6
    assert p[1] == pytest.approx(0.5) and p[2] == pytest.approx(0.5)
    v = stats.verdict([0.001, 0.001, 0.5, 0.5], [0.001, 0.5, 0.001, 0.5])
    assert list(v) == ["real but negligible", "meaningful difference", "no effect (equivalent)", "inconclusive"]


def test_bh_and_wald_equal():
    adj = stats.bh([0.01, 0.02, np.nan, 0.04])
    assert np.isnan(adj[2]) and (adj[[0, 1, 3]] >= [0.01, 0.02, 0.04]).all()
    params = pd.Series([0.2, 0.2, 0.2], index=list("abc"))
    cov = pd.DataFrame(np.eye(3) * 0.01, index=list("abc"), columns=list("abc"))
    assert stats.wald_equal(params, cov, list("abc"))["chi2"] == pytest.approx(0.0)
    assert stats.wald_joint(params, cov, list("abc"))["chi2"] == pytest.approx(12.0)    # 3 x 0.2² / 0.01


def test_absorbed_ols_equals_dummy_regression():
    rng = np.random.default_rng(1)
    n = 600
    d = pd.DataFrame({"g": rng.integers(0, 40, n), "c": rng.integers(0, 30, n), "x": rng.integers(0, 2, n)})
    d["y"] = 0.3 * d["x"] + 0.05 * d["g"] + rng.normal(0, 0.1, n)
    fit = stats.absorbed_ols(d, "y", ["x"], ["g"], "c")
    ref = smf.ols("y ~ x + C(g)", d).fit()
    assert fit["table"].set_index("term").loc["x", "estimate"] == pytest.approx(ref.params["x"])
    assert fit["table"]["ci_low"].iat[0] < 0.3 < fit["table"]["ci_high"].iat[0]


def test_crossed_mixed_recovers_a_planted_partner_effect():
    rng = np.random.default_rng(2)
    dogs = pd.DataFrame({"dog": range(30), "trait": np.repeat([0, 1], 15), "u": rng.normal(0, 0.05, 30)})
    rows = pd.DataFrame({"dog_key": rng.integers(0, 30, 3000), "prev_dog_key": rng.integers(0, 30, 3000)})
    rows["trait"] = dogs["trait"].to_numpy()[rows["prev_dog_key"]]
    rows["y"] = (0.10 * rows["trait"] + dogs["u"].to_numpy()[rows["dog_key"]]
                 + dogs["u"].to_numpy()[rows["prev_dog_key"]] + rng.normal(0, 0.05, 3000))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = stats.crossed_mixed("y ~ trait", rows, {"dog": "dog_key", "partner": "prev_dog_key"})
    t = stats.mixed_table(fit, ["trait"]).iloc[0]
    assert t["ci_low"] < 0.10 < t["ci_high"]
    # The CI reflects 30 partner dogs, not 3,000 rows: far wider than the naive OLS one.
    naive = smf.ols("y ~ trait", rows).fit().bse["trait"]
    assert t["se"] > 3 * naive


# --- Invariants on the real data ----------------------------------------------------------

@pytest.fixture(scope="module")
def tables():
    return metrics.load_processed()


def test_lanes_are_drawn_per_race(tables):
    s = lane.lane_assignment(tables["heats"])["summary"].set_index("check")["share"]
    assert s.iloc[0] < 0.005                     # lane switches inside a race are rare
    assert s.iloc[1] == pytest.approx(0.5, abs=0.02)
    assert s.iloc[2] == 1.0                       # the first-listed team is always blue


def test_lane_outcomes_give_a_verdict_for_every_row(tables):
    out = lane.lane_outcomes(tables["heats"], tables["runs"], "field")
    allowed = {"real but negligible", "meaningful difference", "no effect (equivalent)", "inconclusive"}
    assert set(out["verdict"]) <= allowed
    assert out["ci_low"].le(out["blue_minus_red"]).all() and out["blue_minus_red"].le(out["ci_high"]).all()


def test_pass_frame_is_wrft_passes_onto_known_dogs(tables):
    f = partner.pass_frame(tables["runs"])
    assert f["is_wrft_dog"].all() and f["position"].between(2, 4).all()
    assert f["prev_category"].isin(partner.CATEGORIES).all()
    assert f["incoming"].notna().all() and f["own"].notna().all()
    # Racing passes and held passes split the timed passes without overlap.
    assert f["pass_s"].dropna().le(metrics.HELD_PASS_S).all()
    assert f.loc[f["held"].eq(1), "pass_s"].isna().all()
    assert (f["pass_s"].notna() | f["held"].eq(1)).sum() == f["pass_all_s"].notna().sum()


def test_competition_days_cover_all_wrft_heats_with_weather(tables):
    h, r = tables["heats"], tables["runs"]
    wx = pd.read_csv(config.PROCESSED / "weather_day.csv")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        idx = competition.speed_index(r[r["is_wrft_dog"]], "WRFT")
    days = competition.competition_days(h, r, wx, lane.lane_by_ring_day(r), idx, idx)
    assert days["heats"].sum() == h[h["is_wrft"] & h["win_value"].notna()].shape[0]
    assert days[["temp_mean_c", "humidity_mean_pct", "wind_mean_ms"]].notna().all().all()
    # The index is centred: an average ring-day is 0 % on the log scale.
    assert np.log1p(idx["pct"] / 100).mean() == pytest.approx(0.0, abs=1e-9)
