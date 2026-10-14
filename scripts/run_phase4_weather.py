"""Phase 4.0: fetch historical weather and attach it to every competition day and heat.

Reads data/processed/competitions.csv and heats.parquet (run scripts/run_phase2_clean.py
first). Raw API responses are cached in data/external/weather/; only missing files are
downloaded, unless --refresh is given. Writes to data/processed/:
  weather_hourly.csv    one row per venue and local hour (event days + the day before)
  weather_day.csv       one row per sheet-day, summarised over the racing window
  heat_weather.parquet  one row per heat (all 4,336), weather at the minute it ran
and the draft figure figures/phase4/weather_strip.png.

Usage:  ~/.local/bin/uv run python scripts/run_phase4_weather.py [--refresh]
"""

import argparse

import pandas as pd

from flyball import config, weather
from flyball.plots import phase4 as plots, style


def build(refresh: bool = False) -> dict:
    comps = pd.read_csv(config.PROCESSED / "competitions.csv")
    heats = pd.read_parquet(config.PROCESSED / "heats.parquet", columns=["heat_id", "comp_day_id", "heat_time"])
    missing = set(comps["venue"]) - set(config.VENUES)
    assert not missing, f"venues without coordinates in config.VENUES: {missing}"

    plan = weather.fetch_plan(comps)
    raw, downloaded = weather.fetch_all(plan, refresh)
    hourly = weather.hourly_table(plan, raw)
    grid = weather.grid_points(plan, raw)

    heats = heats.merge(comps[["comp_day_id", "venue"]], on="comp_day_id", validate="many_to_one")
    heat_wx = weather.heat_weather(heats, hourly)
    heat_wx = heat_wx.merge(heats[["heat_id", "comp_day_id"]].drop_duplicates(), on="heat_id")

    day = weather.day_weather(comps, hourly)
    day = (comps[["comp_day_id", "competition", "ring"]].merge(day, on="comp_day_id")
           .merge(heat_wx.groupby("comp_day_id").size().rename("n_heats").reset_index(), on="comp_day_id")
           .merge(grid.drop(columns="fetch_id").drop_duplicates("venue"), on="venue"))
    day["venue_note"] = day["venue"].map(lambda v: config.VENUES[v]["note"])
    return {"plan": plan, "hourly": hourly, "grid": grid, "heat_weather": heat_wx, "day": day,
            "downloaded": downloaded}


def rounded(df: pd.DataFrame) -> pd.DataFrame:
    """Round the numeric columns only (datetime columns can't be rounded this way)."""
    return df.round({c: 3 for c in df.select_dtypes("number").columns})


def write(out: dict) -> None:
    rounded(out["hourly"]).to_csv(config.PROCESSED / "weather_hourly.csv", index=False)
    rounded(out["day"]).to_csv(config.PROCESSED / "weather_day.csv", index=False)
    rounded(out["heat_weather"]).to_parquet(config.PROCESSED / "heat_weather.parquet", index=False)
    style.apply()
    style.save(plots.weather_strip(out["day"]), "weather_strip", "phase4")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download every response")
    out = build(parser.parse_args().refresh)
    write(out)
    pd.set_option("display.width", 220)
    n_plan = len(out["plan"])
    print(f"Requests: {n_plan} planned, {out['downloaded']} downloaded, {n_plan - out['downloaded']} from cache")
    hw = out["heat_weather"]
    print(f"Hourly rows: {len(out['hourly'])}; heats with weather: {hw['temp_c'].notna().sum()} of {len(hw)}")
    print("\nGrid points used:")
    print(out["grid"].round(3).to_string(index=False))
    print("\nWeather per competition day (racing window):")
    cols = ["comp_day_id", "venue", "date", "race_start", "race_end", "temp_min_c", "temp_max_c",
            "humidity_mean_pct", "wind_mean_ms", "gust_max_ms", "precip_total_mm", "rain_hours",
            "precip_24h_before_mm", "cloud_mean_pct"]
    print(out["day"][cols].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
