"""Phase 5: the impact-ledger engine on hand-built cases, plus invariants on the real outputs."""

import json

import numpy as np
import pandas as pd
import pytest

from flyball import config, metrics, synthesis
from flyball.synthesis import Change


# --- Engine on synthetic inputs ----------------------------------------------------------

def test_thin_hits_the_target_rate_in_both_directions():
    x = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], float)            # 40 % have the fault
    q = synthesis.thin(x, np.array([0.1, 0.4, 0.7]))
    assert q.mean(axis=0) == pytest.approx([0.1, 0.4, 0.7])
    assert (q[:, 1] == x).all()                                     # no change at the current rate
    assert (q[x == 0, 0] == 0).all()                                # going down never adds faults
    assert (q[x == 1, 2] == 1).all()                                # going up never removes them


def _toy_frame(n=400, seed=7):
    """A heat-win model frame with known coefficients: faults cost wins, speed gap too."""
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"speed_gap": rng.normal(0, 1, n), "start_gap": rng.normal(0, 0.05, n),
                      "typ_clean_time": rng.normal(17, 1, n)})
    for c in ["false_start", "pass_fault", "run_fault"]:
        d[f"own_{c}"] = rng.binomial(1, 0.2, n)
        d[f"opp_{c}"] = rng.binomial(1, 0.2, n)
    names = ["Intercept", "speed_gap", "start_gap", "own_false_start", "own_pass_fault", "own_run_fault",
             "opp_false_start", "opp_pass_fault", "opp_run_fault"]
    beta = np.array([[0.0, -0.4, -1.0, -2.0, -2.0, -2.5, 1.0, 1.0, 1.0]])
    draws = beta + rng.normal(0, 0.05, (200, len(names)))
    return {"d": d, "names": names, "beta": beta, "draws": draws, "scale": 1.0}


def test_expected_wins_with_observed_inputs_is_the_model_prediction():
    f = _toy_frame()
    d, names, beta = f["d"], f["names"], f["beta"]
    X = np.column_stack([np.ones(len(d)), d[names[1:]].to_numpy(float)])
    direct = (1 / (1 + np.exp(-X @ beta[0]))).sum()
    assert synthesis.expected_wins(d, names, beta, *synthesis._inputs(d, [], 1, False))[0] == pytest.approx(direct)


def test_lever_effects_have_the_right_sign_and_size():
    f = _toy_frame()
    d = f["d"]
    everywhere = np.ones(len(d), bool)
    none = synthesis.lever_effect(f, [])
    assert none["extra_wins"] == pytest.approx(0) and none["ci_low"] == pytest.approx(0, abs=1e-9)

    fewer = synthesis.lever_effect(f, [Change(everywhere, "own_false_start", -0.1)])
    ceiling = synthesis.lever_effect(f, [Change(everywhere, c, -d[c].mean()) for c in synthesis.OWN_FAULTS])
    more = synthesis.lever_effect(f, [Change(everywhere, "own_false_start", +0.1)])
    faster = synthesis.lever_effect(f, [Change(everywhere, "speed_gap", -0.5)])
    assert 0 < fewer["extra_wins"] < ceiling["extra_wins"]
    assert more["extra_wins"] < 0 < faster["extra_wins"]
    assert fewer["ci_low"] <= fewer["extra_wins"] <= fewer["ci_high"]

    # A reference arm equal to the lever gives exactly nothing.
    arm = [Change(everywhere, "speed_gap", 16.5, set_to=True), Change(everywhere, "own_run_fault", 0.1, set_to=True)]
    assert synthesis.lever_effect(f, arm, reference=arm)["extra_wins"] == pytest.approx(0)


# --- Real data and outputs ------------------------------------------------------------------

@pytest.fixture(scope="module")
def frame():
    return synthesis.ledger_frame(metrics.load_processed())


def test_ledger_frame_is_wrft_against_other_clubs(frame):
    d = frame["d"]
    assert d["team_norm"].str.startswith("wildrunners").all()
    assert not d["opponent_is_wrft"].astype(bool).any()
    assert d[["speed_gap", "start_gap", "typ_clean_time", "temp_c"]].notna().all().all()
    assert 1.0 <= frame["scale"] < 1.05                     # the model keeps nearly every decided heat
    assert d["day1_of_two"].any() and not d["day1_of_two"].all()


@pytest.fixture(scope="module")
def ledger():
    return pd.read_csv(config.REPORTS / "phase5" / "impact_ledger.csv")


def test_ledger_rows_are_consistent(ledger):
    assert ledger["lever_id"].is_unique
    assert (ledger["ci_low"] <= ledger["extra_wins"] + 1e-3).all()
    assert (ledger["extra_wins"] <= ledger["ci_high"] + 1e-3).all()
    assert ledger.loc[ledger["lever_id"].eq("ceiling"), "extra_wins"].iat[0] == ledger["extra_wins"].max()
    gaps = ledger[ledger["lever_id"].str.startswith("gap|")]
    assert (gaps["extra_wins"] >= -1e-9).all()             # closing a gap never costs wins
    club = ledger.set_index("lever_id")["extra_wins"]
    assert club["gap_club|all"] >= club[["gap_club|own_false_start", "gap_club|own_pass_fault",
                                         "gap_club|own_run_fault"]].max()


def test_key_numbers_resolve_and_match_the_ledger(ledger):
    keys = synthesis.key_numbers()
    saved = json.loads((config.REPORTS / "phase5" / "key_numbers.json").read_text(encoding="utf-8"))
    assert saved == json.loads(json.dumps(keys))           # the committed JSON is up to date
    by_id = ledger.set_index("lever_id")
    for key, lever_id in synthesis.LEDGER_KEYS.items():
        assert keys[key]["value"] == pytest.approx(by_id.at[lever_id, "extra_wins"])
    for k in keys.values():
        assert k["source"].startswith("reports/") and k["log_step"]
        if "ci" in k:
            assert k["ci"][0] <= k["value"] <= k["ci"][1]
