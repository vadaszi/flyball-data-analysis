"""Project-wide constants: file paths, cell encodings, code maps and thresholds.

Everything a reader might want to tweak lives here, so the other modules
contain logic only. See `data_structure.md` and `domain_knowledge.md` for
where each value comes from.
"""

from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]

DOGS_XLSX = ROOT / "Wild_Runners_Flyball_Team_kutyak_alapadatai.xlsx"
COMPETITION_XLSX = {
    "CZ": ROOT / "FLYBALLCZ_versenyadatok.xlsx",
    "EFC": ROOT / "EFC_versenyadatok.xlsx",
}

PROCESSED = ROOT / "data" / "processed"
EXTERNAL = ROOT / "data" / "external"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"

# --- Competition sheet layout ----------------------------------------------
TITLE_CELL = "B1"
FIRST_DATA_ROW = 3

# Columns A..T by position (headers repeat, so names are ours, not Excel's).
SHEET_COLUMNS = [
    "row_no",     # A  running number
    "division",   # B
    "when",       # C  time of day
    "team",       # D  font colour = lane
    "opponent",   # E
    "total",      # F
    "outcome",    # G
    "hurdle_cm",  # H
    "name1", "start", "run1",          # I J K
    "name2", "chg2", "run2",           # L M N
    "name3", "chg3", "run3",           # O P Q
    "name4", "chg4", "run4",           # R S T
]
TEAM_COL = SHEET_COLUMNS.index("team") + 1          # 1-based column index of D
TIME_COLUMNS = ["start", "run1", "chg2", "run2", "chg3", "run3", "chg4", "run4"]
NAME_COLUMNS = ["name1", "name2", "name3", "name4"]

# --- Font colours ------------------------------------------------------------
# Colours are resolved to a 6-digit RGB hex first (CZ uses rgb, EFC uses a
# custom indexed palette: 11 = red, 15 = blue), so one map serves both files.
LANE_BY_RGB = {"FF0000": "red", "0000FF": "blue"}
FAULT_FONT_RGB = "FF0000"

# --- Text codes in time cells --------------------------------------------------
# Raw spelling (lower-cased, stripped) -> canonical code.
TEXT_CODES = {
    "ok": "ok",            # ~0.00 s pass ("perfect")
    "chyba": "error",      # early pass detected but not quantified
    "error": "error",
    "mimo": "outside",     # dog went outside / missed a hurdle
    "outside": "outside",
    "vběhl": "run_in",     # dog ran in / behind the box
    "vbehl": "run_in",
    "run in": "run_in",
    "ran in": "run_in",
}

# Outcome letters: Czech V/P/R and English W/L/T.
OUTCOMES = {"V": "win", "W": "win", "P": "loss", "L": "loss", "R": "tie", "T": "tie"}

# --- Titles and dates ----------------------------------------------------------
HUNGARIAN_MONTHS = {
    "január": 1, "február": 2, "március": 3, "április": 4, "május": 5, "június": 6,
    "július": 7, "augusztus": 8, "szeptember": 9, "október": 10, "november": 11,
    "december": 12,
}
COUNTRY_BY_FILE = {"CZ": "CZ", "EFC": "HU"}

# Manual corrections to competition dates, keyed by sheet name. Filled only
# when an external source contradicts the title (see ANALYSIS_LOG.md).
# Czech championship: the title says 3-4 Sep (Sun-Mon), but the Hop Trop club
# results page gives 2-3 Sep 2023 (Sat-Sun) and its best times match our data
# exactly (Step 1.9). https://www.hoptropflyball.cz/uspechy-2/
DATE_OVERRIDES: dict[str, list[str]] = {
    "Mistrovství České republiky": ["2023-09-02", "2023-09-03"],
}

# --- Teams and dogs --------------------------------------------------------------
WRFT_PREFIX = "WildRunners"

# Decimal-point / unit entry errors in ulna length (cm), confirmed by the FCI table.
ULNA_CORRECTIONS = {"Speedy": 14.91, "Henry": 12.09, "Bruno": 17.55, "Falco": 15.28}

# FCI ulna table: (upper limit inclusive, jump height). A value exactly on a
# limit gets the lower height.
FCI_ULNA_TABLE = [
    (10.00, 15.0), (11.25, 17.5), (12.50, 20.0), (13.75, 22.5),
    (15.00, 25.0), (16.25, 27.5), (17.50, 30.0), (float("inf"), 32.5),
]

MIN_AGE_MONTHS = 18

# --- Plausibility thresholds (seconds) ------------------------------------------
ROUND_DP = 3
IDENTITY_TOL = 0.04        # total = start + 7 parts, each displayed to 0.01 s: max rounding error 8 x 0.005
MIN_RUN = 3.3              # fastest dog ever recorded is 3.383 s
PRACTICE_MAX_TOTAL = 8.0   # a one-dog practice row can't take longer than this

# Outlier rules (justified in ANALYSIS_LOG Step 1.8)
MAX_RUN = 10.0               # 31 m in 10 s is a trot; 99.9th percentile is 9.1 s
MAX_START = 3.0              # beyond this the dog was held, not raced (99.5th pct 0.8 s)
MAX_PASS = 3.0               # same for changeovers (99th pct 2.6 s)
DOG_OUTLIER_K = 5.0          # per-dog rule: run slower than median + max(K x scaled MAD,
DOG_OUTLIER_MIN_EXCESS = 1.0 #   MIN_EXCESS seconds), for dogs with enough runs
DOG_OUTLIER_MIN_RUNS = 10

# --- Weather (Phase 4.0, ANALYSIS_LOG Step 3) -------------------------------------
# Venue coordinates, keyed by the `venue` string parsed from the sheet titles.
# Hard-coded (not geocoded at run time) so every run uses the same points.
# The three ambiguous names were resolved from the competition context:
# see `note` and `source` for the evidence.
VENUES: dict[str, dict] = {
    "Heroltice": dict(
        lat=49.3114, lon=16.4128, tz="Europe/Prague",
        note="Heroltice, Brno-venkov district (near Tišnov): 'Happy Herolky' dog-sport ground, "
             "Heroltice 65. Not Heroltice in Šumperk, Jihlava or Vyškov districts; a Brno club "
             "calls the event 'on our doorstep'.",
        source="https://flyball.cz/lokace/happy-herolky-kynologicky-areal/ ; "
               "https://flyball-brno.websnadno.cz/202329.html"),
    "Žamberk": dict(
        lat=50.0860, lon=16.4674, tz="Europe/Prague",
        note="Žamberk, Ústí nad Orlicí district (unique match).",
        source="https://flyball.cz/lokace/zamberk/"),
    "Blšany": dict(
        lat=50.2173, lon=13.4712, tz="Europe/Prague",
        note="Blšany, Louny district: football ground, U Stadionu 10, 439 88 (grass pitch). "
             "Not Blšany u Loun.",
        source="https://flyball.cz/lokace/blsany/ ; https://www.flyvaryors.cz/"),
    "Pláně": dict(
        lat=49.9502, lon=13.3082, tz="Europe/Prague",
        note="Pláně, Plzeň-sever district: the airfield near Plzeň where M.E.D.'s Trophy is held.",
        source="https://flyball.cz/akce/m-e-d-s-trophy-2022/ ; "
               "https://flyball-rup.cz/2018/07/03/m-e-d-s-trophy-2/"),
    "Prostějov": dict(
        lat=49.4719, lon=17.1118, tz="Europe/Prague",
        note="Prostějov, KK Prostějov club ground (unique match).",
        source="https://flyball.cz/akce/mistrovstvi-bcccz-ve-flyballu-2023/"),
    "Nové Město pod Smrkem": dict(
        lat=50.9249, lon=15.2294, tz="Europe/Prague",
        note="Nové Město pod Smrkem, Liberec district (unique match).",
        source="Open-Meteo geocoder"),
    "Louňovice": dict(
        lat=49.9823, lon=14.7617, tz="Europe/Prague",
        note="Louňovice, Praha-východ district (near Mukařov). Not Louňovice pod Blaníkem.",
        source="https://flyball.cz/akce/machale-spadlo-ti-to-3/"),
    "Litomyšl": dict(
        lat=49.8681, lon=16.3130, tz="Europe/Prague",
        note="Litomyšl, Svitavy district (unique match).",
        source="Open-Meteo geocoder"),
    "Vodňany": dict(
        lat=49.1479, lon=14.1751, tz="Europe/Prague",
        note="Vodňany, Strakonice district, as in the sheet title. flyball.cz files the event "
             "under České Budějovice (~25 km away, same weather regime).",
        source="https://flyball.cz/akce/budejckej-xtreme-2023/"),
    "Tápiószentmárton": dict(
        lat=47.3399, lon=19.7465, tz="Europe/Budapest",
        note="Tápiószentmárton, Pest county, Hungary (European Flyball Championship 2023).",
        source="https://flyball.cz/akce/european-flyball-championship-2023/"),
}

WEATHER_DIR = EXTERNAL / "weather"
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo hourly variables. Instantaneous ones are the value at the full hour;
# interval ones are the sum (rain) or maximum (gusts) or mean (radiation) over the
# hour *ending* at the timestamp.
WEATHER_INSTANT_VARS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "dew_point_2m",
    "cloud_cover", "wind_speed_10m", "wind_direction_10m",
]
WEATHER_INTERVAL_VARS = ["precipitation", "rain", "wind_gusts_10m", "shortwave_radiation"]
WEATHER_HOURLY_VARS = WEATHER_INSTANT_VARS + WEATHER_INTERVAL_VARS
WEATHER_UNITS = {
    "temperature_2m": "°C", "apparent_temperature": "°C", "relative_humidity_2m": "%",
    "dew_point_2m": "°C", "cloud_cover": "%", "wind_speed_10m": "m/s",
    "wind_direction_10m": "°", "precipitation": "mm", "rain": "mm",
    "wind_gusts_10m": "m/s", "shortwave_radiation": "W/m²",
}
WET_HOUR_MM = 0.1   # an hour with at least this much precipitation counts as a rain hour
