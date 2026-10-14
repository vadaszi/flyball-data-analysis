"""Phase 4B: weather models and line-up search on synthetic data, plus invariants on the real data."""

import warnings

import numpy as np
import pandas as pd
import pytest

from flyball import config, lineup, metrics, stats, weather_effects as we


# --- Helpers on synthetic inputs ---------------------------------------------------------

def test_small_sample_widens_cis_and_linear_combination_adds_terms():
    rng = np.random.default_rng(3)
    d = pd.DataFrame({"g": rng.integers(0, 50, 800), "c": rng.integers(0, 8, 800),
                      "x1": rng.normal(size=800), "x2": rng.normal(size=800)})
    d["y"] = 0.2 * d["x1"] + 0.1 * d["x2"] + rng.normal(0, 0.5, 800)
    normal = stats.absorbed_ols(d, "y", ["x1", "x2"], ["g"], "c")
    small = stats.absorbed_ols(d, "y", ["x1", "x2"], ["g"], "c", small_sample=True)
    assert normal["t_df"] is None and small["t_df"] == 7
    width = lambda f: (f["table"]["ci_high"] - f["table"]["ci_low"]).to_numpy()
    assert (width(small) > width(normal)).all()
    combo = stats.linear_combination(small, {"x1": 1.0, "x2": 1.0})
    assert combo["estimate"] == pytest.approx(small["params"].sum())
    assert stats.tost(0.0, 0.01, 0.05, df=7) > stats.tost(0.0, 0.01, 0.05)       # t tails are heavier


def test_eb_shrink_mean_pulls_small_groups_harder():
    rng = np.random.default_rng(4)
    big = pd.DataFrame({"g": "big", "v": rng.normal(1.0, 0.3, 200)})
    small = pd.DataFrame({"g": "small", "v": [1.0, 1.0]})
    rest = pd.DataFrame({"g": np.repeat(list("abcdefgh"), 30), "v": rng.normal(0.0, 0.3, 240)})
    d = pd.concat([big, small, rest], ignore_index=True)
    out = stats.eb_shrink_mean(d["v"], d["g"])
    pull = (out["raw_mean"] - out["shrunk_mean"]) / out["raw_mean"]
    assert pull["small"] > 5 * pull["big"] > 0


def test_within_competition_recovers_a_planted_heat_effect():
    """Same dog, same event: runs get 2 % slower per 10 °C above 20 °C, and nothing below."""
    rng = np.random.default_rng(5)
    rows = []
    for event in range(10):
        for day in range(2):
            base = rng.uniform(8, 32)
            for heat in range(30):
                temp = base + rng.normal(0, 2)
                for dog in range(8):
                    rows.append({"dog": dog, "event": event, "day": day, "temp_c": temp,
                                 "humidity_pct": rng.uniform(40, 80), "wind_ms": rng.uniform(1, 6),
                                 "precip_3h_mm": rng.choice([0.0, 0.5]), "position": dog % 4 + 1,
                                 "hurdle_step": 0.0, "run_no_today": heat + 1, "day2": float(day)})
    f = pd.DataFrame(rows)
    # 0.02 on the log scale (about 2 %) per 10 °C above 20 °C, nothing below
    f["y"] = 1.4 + 0.02 * np.clip(f["temp_c"] - 20, 0, None) / 10 + 0.01 * f["dog"] + rng.normal(0, 0.03, len(f))
    f = we.add_terms(f).assign(dog_event=lambda x: x["dog"].astype(str) + "|" + x["event"].astype(str),
                               venue_day=lambda x: x["event"].astype(str) + "|" + x["day"].astype(str),
                               run_time=lambda x: np.exp(x["y"]))
    spec = dict(frame=f, unit="log", margin="run_s", level="dog", absorb="dog_event",
                controls=we.DOG_CONTROLS, categorical=("position",), outcome="run time")
    fit = we.fit_spec(spec)
    above = stats.linear_combination(fit, {"temp10": 1, "hot10": 1})
    below = stats.linear_combination(fit, {"temp10": 1})
    # Point estimates, not CI coverage: one draw misses a 95 % CI 1 time in 20 by design.
    assert above["estimate"] == pytest.approx(0.02, abs=0.007)
    assert below["estimate"] == pytest.approx(0.0, abs=0.006)
    assert fit["n_clusters"] == 20


def _toy_profiles() -> pd.DataFrame:
    """Six dogs: A-D fast at 25 cm, E slow, F small (15 cm) and slow; only A and E may start."""
    prof = pd.DataFrame({
        "dog": list("ABCDEF"), "height_cm": [25.0, 25, 25, 25, 25, 15],
        "can_start": [True, False, False, False, True, False],
        "start_s": [0.05, 0.2, 0.2, 0.2, 0.3, 0.2], "pass_s": [0.3, 0.1, 0.15, 0.2, 0.2, 0.2],
        "false_start_p": 0.0, "early_pass_p": 0.0, "run_fault_p": 0.0, "in_pool": True,
        "speed_u0": np.log([1.0, 1.0, 1.01, 1.02, 1.2, 1.5]), "speed_slope": 0.01,
    })
    prof.attrs.update(speed_base=np.log(4.0), speed_position=(0.0, 0.01, 0.01, 0.01), n_slopes_floored=0)
    return prof


def test_search_finds_the_known_best_line_up():
    top = lineup.search(_toy_profiles(), cost=8.0, top=3)
    assert set(top.loc[0, ["dog1", "dog2", "dog3", "dog4"]]) == set("ABCD")
    assert top.loc[0, "dog1"] == "A"                       # the only fast certified starter
    assert top.attrs["n_sets"] == 15 and top.attrs["n_orders"] == 15 * 24


def test_smallest_dog_sets_the_hurdle_and_order_only_moves_start_pass_and_position():
    prof = _toy_profiles()
    a = lineup._arrays(prof)
    with_f = lineup.score_orders(a, np.array([[0, 1, 2, 5]]), cost=8.0)
    assert with_f["hurdle_cm"][0] == 15.0
    one = lineup.score_orders(a, np.array([[0, 1, 2, 3]]), cost=8.0)
    two = lineup.score_orders(a, np.array([[0, 3, 2, 1]]), cost=8.0)
    assert one["hurdle_cm"][0] == two["hurdle_cm"][0] == 25.0
    # positions 2-4 share one position effect here, so swapping dogs 2-4 changes only the passes
    assert one["runs_s"][0] == pytest.approx(two["runs_s"][0])
    assert one["expected_s"][0] - two["expected_s"][0] == pytest.approx(one["passes_s"][0] - two["passes_s"][0])


# --- Real data -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tables():
    return metrics.load_processed()


@pytest.fixture(scope="module")
def frames(tables):
    heat_wx = pd.read_parquet(config.PROCESSED / "heat_weather.parquet")
    return we.run_frame(tables["runs"], heat_wx), we.heat_frame(tables["heats"], heat_wx)


def test_weather_frame_matches_every_run_and_flags_the_second_day(frames):
    runs_wx, heats_wx = frames
    speed = runs_wx[runs_wx["valid_speed"]]
    assert speed[we.TERMS].notna().all().all()
    assert heats_wx[we.TERMS].notna().all().all()
    days = runs_wx.groupby("comp_day_id")["day2"].agg(["min", "max"])
    assert (days["min"] == days["max"]).all()                          # one flag per ring-day
    efc = runs_wx[runs_wx["competition"].eq("EFC")].groupby("date")["day2"].first()
    assert list(efc) == [0.0, 1.0]                                     # Sat, Sun across the four EFC sheets
    assert runs_wx.groupby(["dog_key", "date"])["run_no_today"].min().eq(1).all()


def test_effects_and_verdicts_are_complete(frames):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        main = we.within_competition(*frames)
    e = main["effects"]
    n_outcomes = len(we.outcome_specs(*frames))
    assert len(e) == 2 * n_outcomes * len(we.CONTRASTS)
    assert (e["ci_low"] <= e["estimate"]).all() and (e["estimate"] <= e["ci_high"]).all()
    assert e["clusters"].le(22).all()                                  # venue-days, not ring-days
    verdict = we.coach_verdict(e)
    assert set(verdict["factor"]) == {"temperature", "humidity", "wind", "rain"}


def test_profiles_cover_the_pool_and_backtest_trains_on_apr_jul_only(tables):
    prof = lineup.dog_profiles(tables["runs"], tables["dogs"], tables["hurdle_check"])
    pool = prof[prof["in_pool"]]
    assert len(pool) == 42
    assert pool[["run_25cm_s", "start_s", "pass_s", "height_cm"]].notna().all().all()
    assert prof[["false_start_p", "early_pass_p", "run_fault_p"]].stack().between(0, 1).all()
    assert (prof["speed_slope"] >= 0).all()
    bt = lineup.backtest(tables["runs"], tables["heats"], tables["dogs"], tables["hurdle_check"])
    assert (pd.to_datetime(bt["heats"]["date"]) >= lineup.BACKTEST_SPLIT).all()
    assert "Easy" in bt["summary"].attrs["unprofiled_dogs"]           # first raced in September
