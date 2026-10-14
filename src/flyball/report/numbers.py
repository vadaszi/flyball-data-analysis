"""Every number the deck and the site print, and how it is printed in Hungarian.

Two sources, both traceable:
- `reports/phase5/key_numbers.json`: the 97 key numbers (unit, CI, source, log step);
- `derived()`: counts and definitions read from the processed tables, the report CSVs and
  the code's own constants (e.g. the line-up pool threshold), each with its source.

Slide text refers to numbers as placeholders, `{key}` or `{key|modifier|...}`, so no number
is ever typed into the text. An unknown key raises an error.

Hungarian style: decimal comma, `40,8%`, `4,28 mp`, `−` (true minus), a narrow no-break space
as the thousands separator, `százalékpont` for percentage points, and the 95 % CI as a plain
range in brackets, `(20–33)` (the slides explain the brackets once, in the footer).
"""

import json
import re
from functools import cache

import pandas as pd

from flyball import config, lineup, metrics

KEY_NUMBERS = config.REPORTS / "phase5" / "key_numbers.json"
MINUS = "−"
NBSP = " "
THIN = " "          # narrow no-break space: thousands separator

PLACEHOLDER = re.compile(r"\{([a-z0-9_.]+)((?:\|[a-z0-9_]+)*)\}")


# --- Plain formatters ------------------------------------------------------------------

def num(x: float, decimals: int = 2, sign: bool = False) -> str:
    """4.28 -> '4,28'; -0.29 -> '−0,29'; 1116 -> '1 116' (narrow no-break space)."""
    if x is None or pd.isna(x):
        return "–"
    s = f"{abs(x):,.{decimals}f}".replace(",", THIN).replace(".", ",")
    if round(abs(x), decimals) == 0:
        return s if not sign else f"±{s}"
    if x < 0:
        return MINUS + s
    return ("+" + s) if sign else s


def pct(share: float, decimals: int = 1, sign: bool = False) -> str:
    """0.4077 -> '40,8%'."""
    return num(100 * share, decimals, sign) + "%"


def pp(share: float, decimals: int = 1, sign: bool = True) -> str:
    """A difference of two shares: 0.16 -> '+16,0 százalékpont'."""
    return num(100 * share, decimals, sign) + f"{NBSP}százalékpont"


def sec(x: float, decimals: int | None = None, sign: bool = False) -> str:
    """Seconds: 4.28 -> '4,28 mp'; small effects get 3 decimals (0.0064 -> '0,006 mp')."""
    if decimals is None:
        decimals = 3 if abs(x) < 0.1 else 2
    return num(x, decimals, sign) + f"{NBSP}mp"


def wins(x: float, sign: bool = True) -> str:
    """Extra heats won per season, rounded: 27.37 -> '+27'."""
    return num(x, 0, sign)


def ci_range(lo: float, hi: float, fmt) -> str:
    """'(20–33)': the 95 % CI with the same number format as the value."""
    sep = f"{NBSP}…{NBSP}" if min(lo, hi) < 0 else "–"      # '−13,4 … −6,7' reads better than '−13,4–−6,7'
    return f"({fmt(lo)}{sep}{fmt(hi)})"


def date_hu(d) -> str:
    """2023-04-22 -> '2023. ápr. 22.'"""
    months = ["jan.", "febr.", "márc.", "ápr.", "máj.", "jún.", "júl.", "aug.", "szept.", "okt.", "nov.", "dec."]
    t = pd.Timestamp(d)
    return f"{t.year}. {months[t.month - 1]} {t.day}."


DAYS_HU = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]


def weekday_hu(d) -> str:
    return DAYS_HU[pd.Timestamp(d).weekday()]


# --- The registry ----------------------------------------------------------------------

@cache
def key_numbers() -> dict:
    return json.loads(KEY_NUMBERS.read_text(encoding="utf-8"))


def _entry(value, unit, source, ci=None) -> dict:
    out = {"value": value, "unit": unit, "source": source}
    if ci is not None:
        out["ci"] = list(ci)
    return out


@cache
def derived() -> dict:
    """Counts and definitions that the slides quote but key_numbers.json does not hold."""
    rp = config.REPORTS
    comps = pd.read_csv(config.PROCESSED / "competitions.csv")
    dq = pd.read_csv(config.PROCESSED / "data_quality.csv").set_index("check")["n"]
    cards = pd.read_csv(rp / "dog_scorecards.csv")
    teams = pd.read_csv(rp / "phase3" / "team_summary.csv")
    ledger = pd.read_csv(rp / "phase5" / "impact_ledger.csv")
    meta = pd.read_csv(rp / "phase5" / "impact_meta.csv").iloc[0]
    lmeta = pd.read_csv(rp / "phase4b" / "lineup_meta.csv").iloc[0]
    sens = pd.read_csv(rp / "phase4b" / "weather_sensitivity.csv")
    lane = pd.read_csv(rp / "phase4a" / "lane_run_effect.csv")
    wday = pd.read_csv(config.PROCESSED / "weather_day.csv")
    ptab = pd.read_csv(rp / "phase4a" / "partner_table.csv").set_index("incoming_category")
    stab = pd.read_csv(rp / "phase4b" / "lineup_stability.csv")
    window = pd.read_csv(rp / "phase3" / "pass_window.csv")
    heats = pd.read_parquet(config.PROCESSED / "heats.parquet", columns=["is_practice"])
    weff = pd.read_csv(rp / "phase4b" / "weather_effects.csv")
    heat_row = weff[(weff["sample"] == "field") & (weff["model"] == "within competition")
                    & (weff["outcome"] == "run time") & weff["contrast"].str.contains("above")].iloc[0]
    cdays = pd.read_csv(rp / "phase4a" / "competition_days.csv")
    below = (cdays["peer_gap_win_rate_p_holm"] < 0.05) & (cdays["peer_gap_win_rate"] < 0)
    d2 = pd.read_csv(rp / "phase5" / "impact_day2_faults.csv").set_index("fault")
    top3 = ledger[ledger["lever_id"].isin(["lineup_reorder|all", "day2", "gap_club|all"])]
    bt = pd.read_csv(rp / "phase4b" / "lineup_backtest.csv").set_index("check").loc["clean heat: model P(clean)"]
    # pass window: the contiguous bins whose expected cost is within 0.15 s of the cheapest bin
    pass_bins = window[window["kind"] == "pass"]
    flat = pass_bins[pass_bins["expected_cost_s"] <= pass_bins["expected_cost_s"].min() + 0.15]
    edges = flat["bin"].str.strip("(]").str.split(",", expand=True).astype(float)
    field_lane = lane[(lane["sample"] == "field") & (lane["model"] == "mixed")].iloc[0]
    wrft_teams = teams[teams["team"].str.startswith("WildRunners")]

    d = {
        "events": _entry(comps["competition"].nunique(), "count", "data/processed/competitions.csv"),
        "sheet_days": _entry(len(comps), "count", "data/processed/competitions.csv"),
        "team_rows": _entry(int((~heats["is_practice"]).sum()), "count",
                            "data/processed/heats.parquet (practice rows excluded)"),
        "practice_rows": _entry(int(heats["is_practice"].sum()), "count", "data/processed/heats.parquet"),
        "rows_realigned": _entry(int(dq.get("rows_realigned", 0)), "count", "data/processed/data_quality.csv"),
        "wrft_teams": _entry(len(wrft_teams), "count", "reports/phase3/team_summary.csv"),
        "wrft_dogs": _entry(len(cards), "count", "reports/dog_scorecards.csv"),
        "field_dogs": _entry(int(field_lane["dogs"]), "count", "reports/phase4a/lane_run_effect.csv"),
        "field_runs": _entry(int(field_lane["runs"]), "count", "reports/phase4a/lane_run_effect.csv"),
        "pool_min_runs": _entry(lineup.POOL_MIN_RUNS, "count", "flyball.lineup.POOL_MIN_RUNS"),
        "min_starts": _entry(lineup.MIN_STARTS, "count", "flyball.lineup.MIN_STARTS"),
        "pool_dogs": _entry(int(lmeta["pool"]), "count", "reports/phase4b/lineup_meta.csv"),
        "ledger_levers": _entry(len(ledger), "count", "reports/phase5/impact_ledger.csv"),
        "ledger_draws": _entry(int(meta["draws"]), "count", "reports/phase5/impact_meta.csv"),
        "held_pass_s": _entry(metrics.HELD_PASS_S, "s", "flyball.metrics.HELD_PASS_S"),
        "lane_margin_s": _entry(0.05, "s", "ANALYSIS_LOG 4.2 (equivalence margin)"),
        "heat_margin_s": _entry(0.20, "s", "ANALYSIS_LOG 5.2 (clean-heat-time margin)"),
        "temp_hinge_c": _entry(20.0, "c", "ANALYSIS_LOG 5.2 (temperature hinge)"),
        "hot_day_c": _entry(22.0, "c", "reports/findings.md F6 (hot-day protocol)"),
        "temp_min_c": _entry(float(wday["temp_min_c"].min()), "c", "data/processed/weather_day.csv"),
        "temp_max_c": _entry(float(wday["temp_max_c"].max()), "c", "data/processed/weather_day.csv"),
        "weather_variants": _entry(int(sens["model"].nunique()) - 1, "count",
                                   "reports/phase4b/weather_sensitivity.csv (variants besides the baseline)"),
        "stability_resamples": _entry(int(stab["reps"].iloc[0]), "count", "reports/phase4b/lineup_stability.csv"),
        "pass_window_lo_s": _entry(float(edges[0].min()), "s", "reports/phase3/pass_window.csv"),
        "pass_window_hi_s": _entry(float(edges[1][edges[1] < float("inf")].max()), "s",
                                   "reports/phase3/pass_window.csv"),
        "intact_male_dogs": _entry(int(ptab.loc["intact male", "incoming_dogs"]), "count",
                                   "reports/phase4a/partner_table.csv"),
        "wrft_passes": _entry(int(ptab["passes"].sum()), "count", "reports/phase4a/partner_table.csv"),
        "fault_cost_round_s": _entry(round(key_numbers()["fault_cost_s"]["value"]), "s",
                                     "key_numbers fault_cost_s, rounded"),
        "lineup_sets": _entry(int(lmeta["sets"]), "count", "reports/phase4b/lineup_meta.csv"),
        # contrast steps used by the weather models (log 5.2)
        "temp_step_c": _entry(10.0, "c", "ANALYSIS_LOG 5.2 (temperature contrast)"),
        "humidity_step_pp": _entry(0.20, "share", "ANALYSIS_LOG 5.2 (humidity contrast, pp)"),
        "wind_step_ms": _entry(3.0, "ms", "ANALYSIS_LOG 5.2 (wind contrast)"),
        "heat_per_heat_s": _entry(float(heat_row["per_heat_s"]), "s", "reports/phase4b/weather_effects.csv"),
        "below_peer_days": _entry(int(below.sum()), "count", "reports/phase4a/competition_days.csv (Holm p < 0.05)"),
        "avoidable_peak_share": _entry(float(cdays["share_losses_avoidable"].max()), "share",
                                       "reports/phase4a/competition_days.csv"),
        "day2_fs_heats": _entry(float(d2.loc["own_false_start", "estimate"]), "share",
                                "reports/phase5/impact_day2_faults.csv",
                                (d2.loc["own_false_start", "ci_low"], d2.loc["own_false_start", "ci_high"])),
        "day2_ep_heats": _entry(float(d2.loc["own_pass_fault", "estimate"]), "share",
                                "reports/phase5/impact_day2_faults.csv",
                                (d2.loc["own_pass_fault", "ci_low"], d2.loc["own_pass_fault", "ci_high"])),
        "levers_sum_pp": _entry(float(top3["club_win_rate_pp"].sum()) / 100, "share",
                                "reports/phase5/impact_ledger.csv (three main levers, summed)"),
        "planning_target_pp": _entry(0.05, "share", "reports/findings.md (judgement: the levers overlap)"),
        "wrft_starts_ok_threshold": _entry(lineup.MIN_STARTS, "count", "flyball.lineup.MIN_STARTS"),
        # back-test of the fault part (Sep-Oct heats, profiles from Apr-Jul)
        "backtest_clean_heats": _entry(int(bt["n"]), "count", "reports/phase4b/lineup_backtest.csv"),
        "backtest_p_clean_predicted": _entry(float(bt["mean_predicted"]), "share", "reports/phase4b/lineup_backtest.csv"),
        "backtest_p_clean_observed": _entry(float(bt["observed"]), "share", "reports/phase4b/lineup_backtest.csv"),
    }
    return d


def registry() -> dict:
    return {**key_numbers(), **derived()}


@cache
def _scorecards() -> pd.DataFrame:
    cards = pd.read_csv(config.REPORTS / "dog_scorecards.csv")
    return cards.set_index(cards["dog"].str.lower())


def _dog_entry(key: str) -> dict:
    """'dog.maggie.starts' -> Maggie's `starts` from the dog scorecards."""
    _, dog, col = key.split(".")
    v = _scorecards().loc[dog, col]
    unit = ("share" if col.endswith(("_rate", "_eb", "_share")) else
            "s" if col.startswith(("median_", "best_", "adj_")) else "count")
    out = _entry(v.item() if hasattr(v, "item") else v, unit, f"reports/dog_scorecards.csv ({col})")
    base = col.removesuffix("_rate")
    if unit == "share" and f"{base}_ci_low" in _scorecards():
        out["ci"] = [float(_scorecards().loc[dog, f"{base}_ci_low"]), float(_scorecards().loc[dog, f"{base}_ci_high"])]
    return out


def get(key: str) -> dict:
    if key.startswith("dog."):
        return _dog_entry(key)
    reg = registry()
    if key not in reg:
        raise KeyError(f"unknown number key: {key!r}")
    return reg[key]


def value(key: str):
    return get(key)["value"]


# --- Placeholder formatting ------------------------------------------------------------

def _default(entry: dict, mods: set[str]):
    """The formatter for an entry's unit, honouring the modifiers."""
    unit = entry["unit"]
    sign = "sign" in mods
    dec = next((int(m[1:]) for m in mods if re.fullmatch(r"d\d", m)), None)
    if "as_pct" in mods:              # a 0-1 number shown as a percentage: R² 0.77 -> '77%'
        return lambda v: num(100 * v, 0 if dec is None else dec, sign) + "%"
    if "pp" in mods:
        if "nounit" in mods:          # number only, so the text can inflect: '+16 százalékponttal'
            return lambda v: num(100 * v, 1 if dec is None else dec, sign="nosign" not in mods)
        return lambda v: pp(v, 1 if dec is None else dec, sign="nosign" not in mods)
    if unit == "share":
        return lambda v: pct(v, 1 if dec is None else dec, sign)
    if unit == "pct":
        return lambda v: num(v, 2 if dec is None else dec, sign) + "%"
    if unit in ("share", "pct") and "nounit" in mods:
        return lambda v: num(100 * v if unit == "share" else v, 1 if dec is None else dec, sign)
    if unit == "s":
        if "nounit" in mods:
            return lambda v: num(v, (3 if abs(v) < 0.1 else 2) if dec is None else dec, sign)
        return lambda v: sec(v, dec, sign)
    if unit == "wins":
        return lambda v: num(v, 0 if dec is None else dec, sign=True if "nosign" not in mods else False)
    if unit == "count":
        return lambda v: num(v, 0 if dec is None else dec, sign)
    if unit == "c":
        return lambda v: num(v, 0 if dec is None else dec, sign) + f"{NBSP}°C"
    if unit == "ms":
        return lambda v: num(v, 0 if dec is None else dec, sign) + f"{NBSP}m/s"
    if unit in ("r2", "r", "auc"):
        return lambda v: num(v, 2 if dec is None else dec, sign)
    return lambda v: str(v)


def _ci_number(entry: dict, mods: set[str]):
    """CI bounds: the value's number format without unit or plus sign ('(KI 9,5–22,5)')."""
    unit = entry["unit"]
    dec = next((int(m[1:]) for m in mods if re.fullmatch(r"d\d", m)), None)
    if unit == "share":
        return lambda v: num(100 * v, 1 if dec is None else dec)
    if unit == "s":
        return lambda v: num(v, (3 if abs(entry["value"]) < 0.1 else 2) if dec is None else dec)
    if unit == "wins":
        return lambda v: num(v, 0 if dec is None else dec)
    return lambda v: num(v, 2 if dec is None else dec)


def fmt(key: str, *mods: str) -> str:
    """Format one registry number. Modifiers: sign, nosign, pp, ci, nounit, as_pct, abs, d0-d3.

    `nounit` drops the unit so the text can add an inflected one ('0,05 mp-nél', 'százalékponttal')."""
    entry = get(key)
    mods = set(mods)
    v = entry["value"]
    if entry["unit"] == "text":
        return str(v).replace(" > ", " › ")
    if "abs" in mods:
        v = abs(v)
    f = _default(entry, mods)
    out = f(v)
    if "ci" in mods:
        if "ci" not in entry:
            raise KeyError(f"{key!r} has no CI")
        lo, hi = entry["ci"]
        if "abs" in mods:
            lo, hi = sorted((abs(lo), abs(hi)))
        out += NBSP + ci_range(lo, hi, _ci_number(entry, mods))
    return out


def render(text: str) -> str:
    """Replace every {key|mods} placeholder in a text with the formatted number."""
    def sub(m):
        mods = [x for x in m.group(2).split("|") if x]
        return fmt(m.group(1), *mods)
    return PLACEHOLDER.sub(sub, text)


def placeholders(text: str) -> list[tuple[str, list[str]]]:
    """All (key, modifiers) used in a text, for the tests."""
    return [(m.group(1), [x for x in m.group(2).split("|") if x]) for m in PLACEHOLDER.finditer(text)]
