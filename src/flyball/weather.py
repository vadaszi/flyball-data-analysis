"""Phase 4.0: historical weather for every competition day, attached to every heat.

Source: the Open-Meteo historical archive (reanalysis, hourly, local time).
Venue coordinates are fixed in `config.VENUES`; raw API responses are cached in
`data/external/weather/`, so the step can be rebuilt offline.
See ANALYSIS_LOG.md Step 3 for the rules and counts.
"""

import json
import unicodedata

import numpy as np
import pandas as pd
import requests

from flyball import config

# Open-Meteo name -> our column name (unit in the name, as elsewhere in the project).
SHORT_NAMES = {
    "temperature_2m": "temp_c",
    "apparent_temperature": "apparent_temp_c",
    "relative_humidity_2m": "humidity_pct",
    "dew_point_2m": "dew_point_c",
    "cloud_cover": "cloud_pct",
    "wind_speed_10m": "wind_ms",
    "wind_direction_10m": "wind_dir_deg",
    "precipitation": "precip_mm",
    "rain": "rain_mm",
    "wind_gusts_10m": "gust_ms",
    "shortwave_radiation": "radiation_wm2",
}
INSTANT = [SHORT_NAMES[v] for v in config.WEATHER_INSTANT_VARS]
INTERVAL = [SHORT_NAMES[v] for v in config.WEATHER_INTERVAL_VARS]


# --- Which weather to fetch ----------------------------------------------------------

def fetch_plan(competitions: pd.DataFrame) -> pd.DataFrame:
    """One request per venue and event: the event's dates plus the day before.

    The extra day lets us measure rain in the 24 h before racing (wet ground).
    Rings at the same venue share one request, so 28 sheet-days need 11 requests.
    """
    c = competitions.assign(date=pd.to_datetime(competitions["date"]))
    plan = (c.groupby(["venue", "competition"], sort=False)["date"]
            .agg(["min", "max"]).reset_index())
    plan["start"] = (plan["min"] - pd.Timedelta(days=1)).dt.date.astype(str)
    plan["end"] = plan["max"].dt.date.astype(str)
    plan["fetch_id"] = [f"{slug(v)}_{s}_{e}" for v, s, e in zip(plan["venue"], plan["start"], plan["end"])]
    return plan[["fetch_id", "venue", "competition", "start", "end"]]


def slug(text: str) -> str:
    """ASCII file-name slug: 'Nové Město pod Smrkem' -> 'nove_mesto_pod_smrkem'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "_".join(ascii_text.lower().split())


# --- Fetching with a file cache ----------------------------------------------------------

def fetch_venue(venue: str, start: str, end: str, refresh: bool = False) -> tuple[dict, bool]:
    """Raw Open-Meteo JSON for one venue and date range. Returns (data, came_from_cache)."""
    path = config.WEATHER_DIR / f"{slug(venue)}_{start}_{end}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8")), True
    v = config.VENUES[venue]
    params = {
        "latitude": v["lat"], "longitude": v["lon"], "timezone": v["tz"],
        "start_date": start, "end_date": end,
        "hourly": ",".join(config.WEATHER_HOURLY_VARS),
        "wind_speed_unit": "ms",
    }
    resp = requests.get(config.WEATHER_API, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    data["request"] = {"url": config.WEATHER_API, **params}   # keep what was asked for
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data, False


def fetch_all(plan: pd.DataFrame, refresh: bool = False) -> tuple[dict[str, dict], int]:
    """Fetch (or read from cache) every planned request. Returns ({fetch_id: data}, n_downloaded)."""
    raw, downloaded = {}, 0
    for row in plan.itertuples():
        raw[row.fetch_id], cached = fetch_venue(row.venue, row.start, row.end, refresh)
        downloaded += not cached
    return raw, downloaded


# --- Raw JSON -> tidy tables -------------------------------------------------------------

def hourly_table(plan: pd.DataFrame, raw: dict[str, dict]) -> pd.DataFrame:
    """One row per venue and local hour, with our column names and rolling rain sums."""
    parts = []
    for row in plan.itertuples():
        data = raw[row.fetch_id]
        units = data["hourly_units"]
        for var, unit in config.WEATHER_UNITS.items():
            assert units[var] == unit, f"{row.fetch_id}: {var} in {units[var]}, expected {unit}"
        h = pd.DataFrame(data["hourly"]).rename(columns=SHORT_NAMES)
        h["time"] = pd.to_datetime(h["time"])
        assert h["time"].diff().dropna().eq(pd.Timedelta(hours=1)).all(), f"{row.fetch_id}: gap in hours"
        # Rain in the hour blocks ending at this time: the last 3 h and the last 24 h.
        h["precip_3h_mm"] = h["precip_mm"].rolling(3, min_periods=3).sum()
        h["precip_24h_mm"] = h["precip_mm"].rolling(24, min_periods=24).sum()
        h.insert(0, "venue", row.venue)
        h.insert(1, "fetch_id", row.fetch_id)
        parts.append(h)
    return pd.concat(parts, ignore_index=True)


def grid_points(plan: pd.DataFrame, raw: dict[str, dict]) -> pd.DataFrame:
    """The venue point we asked for, and the model grid point Open-Meteo answered with."""
    rows = []
    for row in plan.itertuples():
        d, v = raw[row.fetch_id], config.VENUES[row.venue]
        rows.append({"fetch_id": row.fetch_id, "venue": row.venue,
                     "venue_lat": v["lat"], "venue_lon": v["lon"],
                     "grid_lat": d["latitude"], "grid_lon": d["longitude"],
                     "grid_elevation_m": d["elevation"], "timezone": d["timezone"],
                     "grid_distance_km": haversine_km(v["lat"], v["lon"], d["latitude"], d["longitude"])})
    return pd.DataFrame(rows)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return float(6371 * 2 * np.arcsin(np.sqrt(a)))


# --- Weather per heat --------------------------------------------------------------------

def heat_weather(heats: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """Weather at the minute each heat ran. `heats` needs heat_id, venue and heat_time.

    - Instantaneous values (temperature, humidity, wind, ...) are interpolated
      linearly between the two surrounding full hours.
    - Hourly totals and maxima (rain, gusts, radiation) are taken from the hour
      block that contains the heat, i.e. the block ending at the next full hour.
    - Wind direction is interpolated as a vector, so 350° and 10° average to 0°.
    """
    h = heats[["heat_id", "venue", "heat_time"]].drop_duplicates("heat_id").copy()
    parts = []
    for venue, grp in h.groupby("venue", sort=False):
        wx = hourly[hourly["venue"] == venue].sort_values("time")
        x = grp["heat_time"].astype("int64").to_numpy()
        xp = wx["time"].astype("int64").to_numpy()
        assert x.min() >= xp.min() and x.max() <= xp.max(), f"{venue}: heats outside fetched hours"
        out = grp.copy()
        for col in INSTANT:
            if col != "wind_dir_deg":
                out[col] = np.interp(x, xp, wx[col].to_numpy())
        out["wind_dir_deg"] = interp_direction(x, xp, wx["wind_dir_deg"].to_numpy())
        out["hour_block"] = grp["heat_time"].dt.ceil("h")
        block = wx[["time", *INTERVAL, "precip_3h_mm", "precip_24h_mm"]].rename(columns={"time": "hour_block"})
        parts.append(out.merge(block, on="hour_block", how="left", validate="many_to_one"))
    return pd.concat(parts, ignore_index=True).sort_values("heat_id").reset_index(drop=True)


def interp_direction(x, xp, deg) -> np.ndarray:
    """Interpolate compass directions through their unit-vector components."""
    rad = np.radians(deg)
    u, v = np.interp(x, xp, np.sin(rad)), np.interp(x, xp, np.cos(rad))
    return np.degrees(np.arctan2(u, v)) % 360


def attach(df: pd.DataFrame, heat_wx: pd.DataFrame) -> pd.DataFrame:
    """Add the per-heat weather columns to heats or runs (both carry heat_id)."""
    cols = ["heat_id", *INSTANT, *INTERVAL, "precip_3h_mm", "precip_24h_mm"]
    return df.merge(heat_wx[cols], on="heat_id", how="left", validate="many_to_one")


# --- Weather per competition day ---------------------------------------------------------

def day_weather(competitions: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """One row per sheet-day, summarised over its racing window (first to last heat).

    The window runs from the full hour before the first heat to the full hour
    after the last one. Rain totals use the hour blocks inside that window;
    `precip_24h_before_mm` is the rain in the 24 h before the window opened.
    """
    rows = []
    for c in competitions.itertuples():
        first = pd.Timestamp(f"{c.date} {c.first_heat}").floor("h")
        last = pd.Timestamp(f"{c.date} {c.last_heat}").ceil("h")
        wx = hourly[hourly["venue"] == c.venue].set_index("time")
        win = wx.loc[first:last]
        blocks = win.loc[win.index > first]            # hour blocks that overlap racing
        rows.append({
            "comp_day_id": c.comp_day_id, "venue": c.venue, "date": c.date,
            "race_start": first.strftime("%H:%M"), "race_end": last.strftime("%H:%M"),
            "temp_min_c": win["temp_c"].min(), "temp_mean_c": win["temp_c"].mean(),
            "temp_max_c": win["temp_c"].max(), "apparent_temp_max_c": win["apparent_temp_c"].max(),
            "humidity_mean_pct": win["humidity_pct"].mean(), "dew_point_mean_c": win["dew_point_c"].mean(),
            "cloud_mean_pct": win["cloud_pct"].mean(), "radiation_mean_wm2": blocks["radiation_wm2"].mean(),
            "wind_mean_ms": win["wind_ms"].mean(), "gust_max_ms": blocks["gust_ms"].max(),
            "precip_total_mm": blocks["precip_mm"].sum(),
            "rain_hours": int(blocks["precip_mm"].ge(config.WET_HOUR_MM).sum()),
            "precip_24h_before_mm": wx.loc[first, "precip_24h_mm"],
        })
    return pd.DataFrame(rows)
