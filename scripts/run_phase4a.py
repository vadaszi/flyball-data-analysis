"""Phase 4A: the coach's three questions. Rebuilds every 4A table and draft figure.

  Q1  lane colour (red/blue)                       reports/phase4a/lane_*.csv
  Q2  passing onto intact/neutered male/female     reports/phase4a/partner_*.csv
  Q3  every analysis per competition (+ weather)   reports/phase4a/competition_*.csv, dog_by_competition.csv,
                                                   speed_index.csv, season_trend.csv
  draft figures                                    figures/phase4/*.png

Reads data/processed/ (run scripts/run_phase2_clean.py and run_phase4_weather.py first).

Usage:  ~/.local/bin/uv run python scripts/run_phase4a.py
"""

import warnings

import pandas as pd

from flyball import competition, config, lane, metrics, partner
from flyball.plots import phase4 as plots, style

OUT = config.REPORTS / "phase4a"


def build() -> dict[str, pd.DataFrame]:
    """Compute every Phase 4A table."""
    t = metrics.load_processed()
    heats, runs = t["heats"], t["runs"]
    samples = {"field": (heats, runs[runs["dog_key"].notna()]),
               "WRFT": (heats[heats["is_wrft"]], runs[runs["is_wrft_dog"]])}
    out = {}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # MixedLM boundary/convergence chatter
        # Q1 – lane colour
        assignment = lane.lane_assignment(heats)
        out["lane_assignment"] = assignment["summary"]
        out["lane_assignment_wrft_teams"] = assignment["wrft_teams"]
        out["lane_run_effect"] = pd.concat([lane.lane_run_effect(r, s) for s, (_, r) in samples.items()],
                                           ignore_index=True)
        out["lane_outcomes"] = pd.concat([lane.lane_outcomes(h, r, s) for s, (h, r) in samples.items()],
                                         ignore_index=True)
        lane_days = lane.lane_by_ring_day(runs)
        out["lane_by_ring_day"] = lane_days
        out["lane_wrft_dogs"] = lane.wrft_dog_lane_medians(runs)

        # Q2 – passing onto intact/neutered male/female
        frame = partner.pass_frame(runs)
        out["partner_table"] = partner.partner_table(frame)
        models = partner.partner_models(frame)
        out["partner_contrasts"] = models["contrasts"]
        out["partner_joint"] = models["joint"]
        out["partner_interactions"] = partner.partner_interactions(frame)
        out["partner_sensitivity"] = partner.partner_sensitivity(runs, frame)

        # Q3 – per competition
        index = {s: competition.speed_index(r, s) for s, (_, r) in samples.items()}
        out["speed_index"] = pd.concat(index.values(), ignore_index=True)
        weather_day = pd.read_csv(config.PROCESSED / "weather_day.csv")
        out["competition_days"] = competition.competition_days(heats, runs, weather_day, lane_days,
                                                               index["WRFT"], index["field"])
        out["competition_teams"] = competition.competition_teams(heats, runs)
        out["dog_by_competition"] = competition.dog_by_competition(runs)
        out["season_trend"] = pd.concat([competition.season_trend(r, s) for s, (_, r) in samples.items()],
                                        ignore_index=True)
    out["_weather_day"] = weather_day
    return out


def write(out: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        if not name.startswith("_"):
            df.round({c: 4 for c in df.select_dtypes("number").columns}).to_csv(OUT / f"{name}.csv", index=False)

    style.apply()
    style.save(plots.lane_ring_days(out["lane_by_ring_day"], out["lane_run_effect"]), "lane_ring_days", "phase4")
    style.save(plots.lane_dog_slopes(out["lane_wrft_dogs"]), "lane_wrft_dogs", "phase4")
    style.save(plots.partner_forest(out["partner_contrasts"]), "partner_forest", "phase4")
    style.save(plots.competition_small_multiples(out["competition_days"]), "competition_days", "phase4")
    style.save(plots.dog_competition_heatmap(out["dog_by_competition"]), "dog_by_competition", "phase4")


def main() -> None:
    out = build()
    write(out)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 45)
    print(f"Wrote tables to {OUT} and figures to {config.FIGURES / 'phase4'}\n")
    print("Q1 – lane assignment:")
    print(out["lane_assignment"].round(4).to_string(index=False))
    print("\nQ1 – blue minus red, dog run time:")
    print(out["lane_run_effect"].round(4).to_string(index=False))
    het = out["lane_by_ring_day"].attrs["heterogeneity"]
    print(f"   lane effect differs between ring-days: chi2 = {het['chi2']:.1f}, df = {het['df']}, "
          f"p = {het['p_value']:.2g}; largest |effect| = "
          f"{out['lane_by_ring_day']['seconds'].abs().max():.3f} s per run")
    cols = ["sample", "outcome", "red", "blue", "blue_minus_red", "ci_low", "ci_high", "p_holm", "p_tost", "verdict"]
    print("\nQ1 – blue minus red, every outcome:")
    print(out["lane_outcomes"][cols].round(4).to_string(index=False))
    print("\nQ2 – passes by incoming dog's category:")
    print(out["partner_table"].round(3).to_string(index=False))
    print("\nQ2 – does the incoming category matter at all? (joint test per outcome)")
    print(out["partner_joint"].round(4).to_string(index=False))
    cols = ["spec", "outcome", "level", "incoming_dogs", "estimate", "ci_low", "ci_high", "p_holm", "verdict"]
    print("\nQ2 – contrasts against an incoming neutered male:")
    print(out["partner_contrasts"][cols].round(4).to_string(index=False))
    print("\nQ3 – season trend (same dogs, % run time per 30 days):")
    print(out["season_trend"].round(4).to_string(index=False))
    cols = ["competition", "date", "heats", "win_rate", "clean_heat_rate", "median_clean_time",
            "share_losses_avoidable", "speed_index_wrft_pct", "speed_index_field_pct", "temp_mean_c"]
    print("\nQ3 – WRFT per competition day:")
    print(out["competition_days"][cols].assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d")).round(3)
          .to_string(index=False))


if __name__ == "__main__":
    main()
