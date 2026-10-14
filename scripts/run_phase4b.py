"""Phase 4B: the weather analysis (4d) and the ideal line-up (4e). Rebuilds every 4B table and draft figure.

  4d  does the weather change speed and faults?   reports/phase4b/weather_*.csv
  4e  ideal line-up                               reports/phase4b/dog_profiles.csv, lineup_*.csv
  draft figures                                   figures/phase4/weather_*.png, heat_curve.png, lineup_*.png,
                                                  height_dog_tradeoff.png

Reads data/processed/ (run scripts/run_phase2_clean.py and run_phase4_weather.py first).

Usage:  ~/.local/bin/uv run python scripts/run_phase4b.py
"""

import warnings

import pandas as pd

from flyball import competition, config, lineup, metrics, weather_effects as we
from flyball.plots import phase4 as plots, style

OUT = config.REPORTS / "phase4b"
STABILITY_REPS = 50


def build_weather(t: dict) -> dict[str, pd.DataFrame]:
    """Every 4d table."""
    heat_wx = pd.read_parquet(config.PROCESSED / "heat_weather.parquet")
    weather_day = pd.read_csv(config.PROCESSED / "weather_day.csv")
    runs_wx, heats_wx = we.run_frame(t["runs"], heat_wx), we.heat_frame(t["heats"], heat_wx)
    out = {"weather_correlations": we.correlations(heats_wx, weather_day)}

    main = we.within_competition(runs_wx, heats_wx)
    out["weather_effects"] = main["effects"]
    out["weather_controls"] = main["controls"]
    out["weather_verdict"] = we.coach_verdict(main["effects"])
    out["weather_within_day"] = we.within_day(runs_wx, heats_wx)
    out["weather_mixed_wrft"] = we.wrft_mixed(runs_wx)
    out["weather_sensitivity"] = we.sensitivity(runs_wx, heats_wx)

    index_field = competition.speed_index(t["runs"][t["runs"]["dog_key"].notna()], "field")
    meta = we.day_meta(index_field, weather_day)
    out["weather_day_fit"], out["weather_day_coefficients"], out["weather_days"] = (
        meta["fit"], meta["coefficients"], meta["days"])
    out["weather_curve"] = we.temperature_curve(runs_wx)
    gbm = we.gbm_check(runs_wx)
    out["weather_gbm_scores"], out["weather_gbm_importance"], out["weather_gbm_pdp"] = (
        gbm["scores"], gbm["importance"], gbm["pdp"])
    return out


def build_lineup(t: dict) -> dict[str, pd.DataFrame]:
    """Every 4e table."""
    runs, heats, dogs, hurdle_check = t["runs"], t["heats"], t["dogs"], t["hurdle_check"]
    cost = lineup.fault_cost(heats)
    prof = lineup.dog_profiles(runs, dogs, hurdle_check)
    top = lineup.search(prof, cost)
    best = top.iloc[0]
    current = lineup.current_line_ups(runs)
    teams = lineup.team_recommendations(prof, current, cost)
    out = {
        "dog_profiles": prof,
        "lineup_top": top,
        "lineup_speed_only": lineup.search(prof, 0.0, top=10),
        "lineup_dog_frequency": lineup.dog_frequency(top),
        "lineup_reserves": lineup.reserves(prof, best, cost),
        "lineup_teams": teams,
        "lineup_comparison": lineup.comparison(prof, best, teams, cost),
        "lineup_height_dog": lineup.height_dog(prof, cost),
    }
    bt = lineup.backtest(runs, heats, dogs, hurdle_check)
    out["lineup_backtest"] = bt["summary"].assign(
        test_heats=bt["summary"].attrs["test_heats"], heats_with_unprofiled_dog=bt["summary"].attrs["unprofiled"],
        unprofiled_dogs=", ".join(bt["summary"].attrs["unprofiled_dogs"]))
    out["lineup_backtest_heats"], out["lineup_backtest_by_hurdle"], out["lineup_backtest_calibration"] = (
        bt["heats"], bt["by_hurdle"], bt["calibration"])
    st = lineup.stability(runs, dogs, hurdle_check, cost, reps=STABILITY_REPS)
    out["lineup_stability"] = st["summary"]
    out["lineup_stability_dogs"] = st["dogs"]
    out["lineup_meta"] = pd.DataFrame([{"fault_cost_s": cost, "pool": top.attrs["pool"], "sets": top.attrs["n_sets"],
                                  "orders": top.attrs["n_orders"], "slopes_floored": prof.attrs["n_slopes_floored"]}])
    return out


def build() -> dict[str, pd.DataFrame]:
    t = metrics.load_processed()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # MixedLM boundary/convergence chatter
        return {**build_weather(t), **build_lineup(t)}


def write(out: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.round({c: 4 for c in df.select_dtypes("number").columns}).to_csv(OUT / f"{name}.csv", index=False)

    style.apply()
    style.save(plots.weather_forest(out["weather_effects"]), "weather_forest", "phase4")
    style.save(plots.heat_curve(out["weather_curve"], out["weather_gbm_pdp"]), "heat_curve", "phase4")
    style.save(plots.weather_vs_venue(out["weather_days"]), "weather_vs_venue", "phase4")
    style.save(plots.lineup_breakdown(out["lineup_comparison"]), "lineup_breakdown", "phase4")
    style.save(plots.height_dog_tradeoff(out["lineup_height_dog"]), "height_dog_tradeoff", "phase4")
    style.save(plots.lineup_backtest(out["lineup_backtest_heats"]), "lineup_backtest", "phase4")


def main() -> None:
    out = build()
    write(out)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 70)
    print(f"Wrote tables to {OUT} and figures to {config.FIGURES / 'phase4'}\n")
    print("4d – the coach's weather factors (field, within competition):")
    print(out["weather_verdict"][["factor", "speed", "reliability", "field_run_effect"]].to_string(index=False))
    cols = ["sample", "outcome", "contrast", "estimate", "ci_low", "ci_high", "p_holm", "verdict"]
    e = out["weather_effects"]
    print("\n4d – run time and clean heat time:")
    print(e[e["outcome"].isin(["run time", "clean heat time"])][cols].round(4).to_string(index=False))
    c = out["weather_controls"]
    print("\n4d – the second day of an event (control term):")
    print(c[c["control"].eq("second day of the event")][["sample", "outcome", "estimate", "ci_low", "ci_high"]]
          .round(4).to_string(index=False))
    print("\n4d – how much of the day-to-day speed differences weather explains:")
    print(out["weather_day_fit"].round(3).to_string(index=False))
    print("\n4d – gradient-boosting check (leave one competition out):")
    print(out["weather_gbm_scores"].round(4).to_string(index=False))

    m = out["lineup_meta"].iloc[0]
    print(f"\n4e – searched {int(m['sets']):,} sets / {int(m['orders']):,} orders from {int(m['pool'])} dogs; "
          f"fault cost {m['fault_cost_s']:.2f} s")
    cols = ["rank", "line_up", "expected_s", "no_fault_s", "p_clean", "hurdle_cm"]
    print(out["lineup_top"][cols].head(10).round(3).to_string(index=False))
    print("\n4e – reserves:")
    print(out["lineup_reserves"].round(3).to_string(index=False))
    cols = ["team", "current_order", "current_expected_s", "best_order", "gain_from_order_s", "best_bench_swap",
            "gain_from_swap_s"]
    print("\n4e – current teams:")
    print(out["lineup_teams"][cols].round(3).to_string(index=False))
    cols = ["height_dog", "height_cm", "run_at_own_height_s", "expected_s", "hurdle_saving_s", "gain_vs_without_s"]
    print("\n4e – height dog:")
    print(out["lineup_height_dog"][cols].round(3).to_string(index=False))
    print("\n4e – back-test (profiles Apr–Jul, heats Sep–Oct):")
    print(out["lineup_backtest"].drop(columns=["unprofiled_dogs"]).round(4).to_string(index=False))
    print("\n4e – stability:")
    print(out["lineup_stability"].to_string(index=False))
    print(out["lineup_stability_dogs"].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
