"""Phase 3 metrics: hand-built cases for the logic, plus invariants on the real data."""

import numpy as np
import pandas as pd
import pytest

from flyball import metrics, stats


# --- Helpers on small, hand-built inputs ----------------------------------------------

def test_wilson_ci_known_values():
    lo, hi = stats.wilson_ci([5], [10])
    assert lo[0] == pytest.approx(0.2366, abs=1e-4)
    assert hi[0] == pytest.approx(0.7634, abs=1e-4)
    lo, hi = stats.wilson_ci([0], [20])
    assert lo[0] == 0 and 0 < hi[0] < 0.2


def test_eb_shrinkage_pulls_small_samples_towards_the_mean():
    k = np.array([0, 10, 20, 30, 0])
    n = np.array([100, 100, 100, 100, 3])
    eb = stats.eb_shrink_rate(k, n)
    mean = k[:4].sum() / n[:4].sum()
    # The 3-attempt dog with 0 faults is pulled much further than the 100-attempt one.
    assert eb[4] > eb[0]
    assert abs(eb[4] - mean) < abs(0 - mean)
    assert np.isnan(stats.eb_shrink_rate([1, 0], [5, 0])[1])


def test_holm_is_monotone_and_nan_safe():
    adj = stats.holm([0.01, 0.04, np.nan, 0.03])
    assert np.isnan(adj[2])
    assert adj[0] == pytest.approx(0.03)
    assert all(adj[[0, 1, 3]] >= [0.01, 0.04, 0.03])


def test_auc_perfect_and_random():
    assert stats.auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert stats.auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_loo_median_leaves_the_row_out():
    v = pd.Series([1.0, 2.0, 3.0, np.nan, 10.0])
    g = pd.Series(["a", "a", "a", "a", "b"])
    out = metrics.loo_median(v, g)
    assert out.tolist()[:4] == [2.5, 2.0, 1.5, 2.0]
    assert np.isnan(out.iloc[4])                   # nobody else in group b


def _heat(heat_id, team, opp, outcome, faults=0, rerun=False, complete=True, total=18.0):
    return {"row_id": heat_id * 2 + (team > opp), "heat_id": heat_id, "team": team,
            "team_norm": team, "opponent": opp, "paired": True, "outcome": outcome,
            "n_faults": faults, "rerun": rerun, "any_fault": faults > 0,
            "is_complete": complete, "total": total, "typ_clean_total": 17.0,
            "is_wrft": False}


def test_fault_attribution_labels():
    rows = [
        _heat(0, "A", "B", "win"), _heat(0, "B", "A", "loss"),                       # clean win / slower
        _heat(1, "A", "B", "win", faults=1, rerun=True), _heat(1, "B", "A", "loss", faults=1),
        _heat(2, "A", "B", "loss"), _heat(2, "B", "A", "loss"),                      # break-out-like
        _heat(3, "A", "B", "loss", rerun=True), _heat(3, "B", "A", "win", total=17.5),
        _heat(4, "A", "B", "loss", complete=False), _heat(4, "B", "A", "win"),
    ]
    h = pd.DataFrame(rows)
    for col in metrics.OPP_COLUMNS:
        if col not in h:
            h[col] = np.nan
    a = metrics.fault_attribution(h).set_index(["heat_id", "team"])["reason"]
    assert a[(0, "A")] == "win_clean" and a[(0, "B")] == "loss_slower"
    assert a[(1, "A")] == "win_after_fault" and a[(1, "B")] == "loss_fault"
    assert a[(2, "A")] == "loss_breakout_like"
    assert a[(3, "A")] == "loss_uncoded_rerun"
    assert a[(4, "A")] == "loss_not_finished"


def test_faulted_loss_is_avoidable_only_if_typical_clean_total_would_win():
    rows = [_heat(0, "A", "B", "loss", faults=1), _heat(0, "B", "A", "win", total=17.5),
            _heat(1, "A", "B", "loss", faults=1), _heat(1, "B", "A", "win", total=16.5)]
    h = pd.DataFrame(rows)
    for col in metrics.OPP_COLUMNS:
        if col not in h:
            h[col] = np.nan
    a = metrics.fault_attribution(h).set_index(["heat_id", "team"])["avoidable"]
    assert a[(0, "A")]                 # typical 17.0 s beats the winner's 17.5 s
    assert not a[(1, "A")]             # but not the winner's 16.5 s


# --- Invariants on the real data -----------------------------------------------------------

@pytest.fixture(scope="module")
def tables():
    return metrics.load_processed()


def test_no_practice_rows_and_ties_count_half(tables):
    h = tables["heats"]
    assert not h["is_practice"].any()
    assert set(h.loc[h["outcome"].eq("tie"), "win_value"]) == {0.5}


def test_attribution_covers_every_decided_row_once(tables):
    h = tables["heats"]
    a = metrics.fault_attribution(h)
    assert len(a) == h["outcome"].isin(["win", "loss"]).sum()
    assert a["row_id"].is_unique
    assert set(a["reason"]) <= set(metrics.OUTCOME_LABELS)
    assert not (a["avoidable"] & a["reason"].ne("loss_fault")).any()


def test_heat_view_pairs_each_row_with_its_opponent(tables):
    v = metrics.heat_view(tables["heats"])
    assert (v["team_norm"] != v["opp_team_norm"]).all()
    assert v.groupby("heat_id").size().eq(2).all()


def test_dog_scorecard_rates_are_valid(tables):
    runs = tables["runs"]
    card = metrics.dog_scorecard(runs[runs["is_wrft_dog"]], tables["dogs"])
    assert len(card) == 50 and card["dog"].is_unique
    rates = card.filter(regex="_(rate|eb|ci_low|ci_high)$")
    assert ((rates >= 0) & (rates <= 1) | rates.isna()).all().all()
    assert (card["best_run_p05"] <= card["median_run"]).all()


def test_pass_window_bins_partition_dogs(tables):
    for kind in ("start", "pass"):
        prof = metrics.pass_profile(tables["runs"], kind)
        win = metrics.pass_window(prof, kind, fault_cost_s=8.0)
        assert win["attempts"].sum() == prof["attempts"].sum()
        assert win["is_window"].sum() == 1
