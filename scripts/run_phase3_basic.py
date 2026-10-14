"""Phase 3: basic analyses. Rebuilds every Phase 3 table and draft figure.

Reads data/processed/ (run scripts/run_phase2_clean.py first) and writes
  reports/phase3/*.csv, reports/dog_scorecards.csv, figures/phase3/*.png

Usage:  ~/.local/bin/uv run python scripts/run_phase3_basic.py
"""

import warnings

import pandas as pd

from flyball import config, metrics, stats
from flyball.plots import phase3 as plots, style

OUT = config.REPORTS / "phase3"


def build() -> dict[str, pd.DataFrame]:
    """Compute every Phase 3 table."""
    t = metrics.load_processed()
    heats, runs, dogs = t["heats"], t["runs"], t["dogs"]
    wrft_heats, wrft_runs = heats[heats["is_wrft"]], runs[runs["is_wrft"]]
    view = metrics.heat_view(heats)
    out = {}

    # What wins heats
    out["win_by_fault_status"] = metrics.win_by_fault_status(view)
    out["win_by_speed_gap"] = metrics.win_by_speed_gap(view)
    models = {"field": stats.heat_win_models(metrics.heat_model_frame(view)),
              "wrft": stats.heat_win_models(metrics.heat_model_frame(view, wrft_focal=True))}
    out["heat_win_model"] = pd.concat(
        [stats.coef_table(m["fits"]["full"], exp=True).assign(sample=k) for k, m in models.items()])
    out["heat_win_model_fit"] = pd.concat([m["comparison"].assign(sample=k) for k, m in models.items()])

    # Why heats are lost, and what a fault costs
    attr = metrics.fault_attribution(heats)
    attr["group"] = attr["team"].where(attr["is_wrft"], "Field (non-WRFT)")
    out["fault_attribution"] = pd.concat([
        metrics.attribution_summary(attr, ["group"]),
        metrics.attribution_summary(attr[attr["is_wrft"]].assign(group="WRFT (all teams)"), ["group"]),
    ], ignore_index=True)
    out["fault_cost"] = metrics.fault_cost_seconds(heats)

    # Team level
    out["team_summary"] = pd.concat([
        metrics.team_summary(wrft_heats, wrft_runs, ["team"]),
        metrics.team_summary(heats.assign(team=heats["is_wrft"].map({True: "WRFT (all teams)",
                                                                     False: "Field (non-WRFT)"})),
                             runs.assign(team=runs["is_wrft"].map({True: "WRFT (all teams)",
                                                                   False: "Field (non-WRFT)"})),
                             ["team"]),
    ], ignore_index=True)
    out["peer_benchmark"] = metrics.peer_benchmark(heats)
    out["division_ranks"] = metrics.division_ranks(heats)

    # Starts and passes
    cost = out["fault_cost"].set_index("fault")["rerun_seconds_median"]
    profiles = {"start": metrics.pass_profile(runs, "start"), "pass": metrics.pass_profile(runs, "pass")}
    out["pass_window"] = pd.concat([
        metrics.pass_window(profiles["start"], "start", cost["false_start"]),
        metrics.pass_window(profiles["pass"], "pass", cost["pass_fault"]),
    ], ignore_index=True)

    # Dog level
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # MixedLM boundary/convergence chatter
        dog_models = {"WRFT": stats.dog_run_model(runs[runs["is_wrft_dog"]]),
                      "Field": stats.dog_run_model(runs[runs["dog_key"].notna()])}
    out["dog_effects"] = pd.concat([m["effects"].assign(group=g) for g, m in dog_models.items()],
                                   ignore_index=True)
    card = metrics.dog_scorecard(runs[runs["is_wrft_dog"]], dogs)
    card = card.merge(dog_models["WRFT"]["adjusted_speed"].rename_axis("dog").reset_index(), on="dog", how="left")
    out["dog_scorecards"] = card

    out["sensitivity"] = metrics.sensitivity(heats, runs)
    out["_profiles"] = profiles
    return out


def write(out: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        if name.startswith("_"):
            continue
        path = config.REPORTS / "dog_scorecards.csv" if name == "dog_scorecards" else OUT / f"{name}.csv"
        df.round(4).to_csv(path, index=False)

    style.apply()
    fa = out["fault_attribution"]
    order = [*sorted(g for g in fa["group"] if g.startswith("WildRunners")), "WRFT (all teams)", "Field (non-WRFT)"]
    fa = fa.set_index("group").loc[order].reset_index()
    fa["label"] = fa["group"].map(plots.short_team)
    style.save(plots.heat_outcomes(fa, "label"), "heat_outcomes")
    style.save(plots.what_wins(out["win_by_fault_status"], out["win_by_speed_gap"]), "what_wins")
    style.save(plots.team_quadrant(out["peer_benchmark"]), "team_quadrant")
    style.save(plots.pass_window(out["pass_window"], out["_profiles"]), "pass_window")
    style.save(plots.dog_quadrant(out["dog_scorecards"]), "dog_quadrant")
    style.save(plots.dog_effects(out["dog_effects"]), "dog_effects")


def main() -> None:
    out = build()
    write(out)
    pd.set_option("display.width", 200)
    print(f"Wrote tables to {OUT} and figures to {config.FIGURES / 'phase3'}\n")
    print("Heat-win model fit (speed vs faults):")
    print(out["heat_win_model_fit"].round(3).to_string(index=False))
    print("\nWhy heats are won/lost:")
    print(out["fault_attribution"].round(3).to_string(index=False))
    print("\nFault cost:")
    print(out["fault_cost"].round(3).to_string(index=False))
    print("\nSensitivity:")
    print(out["sensitivity"].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
