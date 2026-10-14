"""Phase 4.0 weather: hand-built cases for the join rules, plus invariants on the real data.

The real-data tests read the files written by scripts/run_phase4_weather.py and are
skipped if they are missing (e.g. before the first fetch).
"""

import numpy as np
import pandas as pd
import pytest

from flyball import config, weather


# --- Join rules on a tiny hand-built hourly table -------------------------------------

def tiny_hourly() -> pd.DataFrame:
    times = pd.date_range("2023-05-06 08:00", periods=4, freq="h")
    h = pd.DataFrame({"venue": "X", "time": times})
    for col in weather.INSTANT + weather.INTERVAL:
        h[col] = 0.0
    h["temp_c"] = [10.0, 12.0, 14.0, 16.0]
    h["wind_dir_deg"] = [350.0, 10.0, 90.0, 90.0]
    h["precip_mm"] = [0.0, 1.0, 2.0, 3.0]          # rain in the hour ending at `time`
    h["precip_3h_mm"] = h["precip_mm"].rolling(3).sum()
    h["precip_24h_mm"] = np.nan
    return h


def test_instant_values_are_interpolated_to_the_minute():
    heats = pd.DataFrame({"heat_id": [1, 2], "venue": "X",
                          "heat_time": pd.to_datetime(["2023-05-06 08:30", "2023-05-06 09:00"])})
    out = weather.heat_weather(heats, tiny_hourly())
    assert out["temp_c"].tolist() == pytest.approx([11.0, 12.0])


def test_wind_direction_is_interpolated_as_a_vector():
    heats = pd.DataFrame({"heat_id": [1], "venue": "X", "heat_time": pd.to_datetime(["2023-05-06 08:30"])})
    out = weather.heat_weather(heats, tiny_hourly())
    # Halfway between 350° and 10° is north (0°), not 180°.
    assert min(out["wind_dir_deg"].iloc[0], 360 - out["wind_dir_deg"].iloc[0]) == pytest.approx(0, abs=1e-6)


def test_rain_comes_from_the_hour_block_containing_the_heat():
    heats = pd.DataFrame({"heat_id": [1, 2], "venue": "X",
                          "heat_time": pd.to_datetime(["2023-05-06 08:10", "2023-05-06 10:00"])})
    out = weather.heat_weather(heats, tiny_hourly())
    # 08:10 lies in the block 08:00-09:00, reported at 09:00; 10:00 closes the block 09:00-10:00.
    assert out["precip_mm"].tolist() == [1.0, 2.0]
    assert out["precip_3h_mm"].tolist()[1] == 3.0


def test_heats_outside_the_fetched_hours_are_refused():
    heats = pd.DataFrame({"heat_id": [1], "venue": "X", "heat_time": pd.to_datetime(["2023-05-06 12:30"])})
    with pytest.raises(AssertionError):
        weather.heat_weather(heats, tiny_hourly())


def test_slug_is_ascii():
    assert weather.slug("Nové Město pod Smrkem") == "nove_mesto_pod_smrkem"
    assert weather.slug("Tápiószentmárton") == "tapioszentmarton"


# --- Invariants on the real data -----------------------------------------------------------

@pytest.fixture(scope="module")
def real():
    paths = {k: config.PROCESSED / f for k, f in [("hourly", "weather_hourly.csv"), ("day", "weather_day.csv"),
                                                  ("heat", "heat_weather.parquet")]}
    if not all(p.exists() for p in paths.values()):
        pytest.skip("weather outputs missing: run scripts/run_phase4_weather.py")
    return {
        "hourly": pd.read_csv(paths["hourly"], parse_dates=["time"]),
        "day": pd.read_csv(paths["day"]),
        "heat": pd.read_parquet(paths["heat"]),
        "heats": pd.read_parquet(config.PROCESSED / "heats.parquet", columns=["heat_id", "comp_day_id"]),
        "comps": pd.read_csv(config.PROCESSED / "competitions.csv"),
    }


def test_every_venue_has_coordinates(real):
    assert set(real["comps"]["venue"]) <= set(config.VENUES)


def test_28_sheet_days_share_22_venue_days(real):
    day = real["day"]
    assert len(day) == 28 and day["comp_day_id"].is_unique
    assert len(day[["venue", "date"]].drop_duplicates()) == 22
    # Rings at the same venue on the same day see the same weather.
    per_day = day.groupby(["venue", "date"])[["temp_max_c", "precip_24h_before_mm"]].nunique()
    assert per_day.max().max() == 1


def test_every_heat_has_weather(real):
    heat = real["heat"]
    assert set(heat["heat_id"]) == set(real["heats"]["heat_id"])
    assert heat["heat_id"].is_unique
    cols = weather.INSTANT + weather.INTERVAL + ["precip_3h_mm", "precip_24h_mm"]
    assert heat[cols].notna().all().all()


def test_values_are_plausible(real):
    h = real["hourly"]
    assert h["temp_c"].between(-5, 40).all()
    assert h["humidity_pct"].between(0, 100).all()
    assert h["cloud_pct"].between(0, 100).all()
    assert (h["precip_mm"] >= 0).all() and (h["rain_mm"] <= h["precip_mm"] + 1e-9).all()
    assert h["wind_ms"].between(0, 25).all() and h["gust_ms"].between(0, 40).all()
    assert (h["gust_ms"] >= h["wind_ms"] - 0.5).all()   # gust = hourly max, wind = value at the hour
    assert h["wind_dir_deg"].between(0, 360).all()


def test_local_time_is_right(real):
    # If the time zone were wrong, the daily temperature peak would drift from the afternoon.
    h = real["hourly"]
    peak_hour = h.loc[h.groupby([h["venue"], h["time"].dt.date])["temp_c"].idxmax(), "time"].dt.hour
    assert 12 <= peak_hour.median() <= 18
