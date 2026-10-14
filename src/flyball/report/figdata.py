"""Small derived tables behind the Phase 6 charts and the website.

Everything here is a re-shaping of the processed tables or the Phase 3-5 report CSVs;
no new statistics are estimated. The deck charts (`plots/deck.py`) and the site
(`report/site.py`) both read from these functions, so they always agree.
"""

from functools import cache

import pandas as pd

from flyball import config, metrics
from flyball.report import numbers

RP = config.REPORTS

TEAM_ORDER = ["Hopefuls", "Dreamers", "Nightfall", "Maximini", "XXL", "Zephyr", "Wonders"]


def short_team(name: str) -> str:
    """'WildRunners dreamers' / 'wildrunners xxl' -> 'Dreamers' / 'XXL'."""
    short = name.lower().replace("wildrunners", "").strip()
    return "XXL" if short == "xxl" else short.capitalize()


def short_competition(name: str) -> str:
    return {"Mistrovství České republiky": "Cseh bajnokság", "Máchale, spadlo ti to!": "Máchale",
            "BCCCZ mistrovství": "BCCCZ bajnokság", "Flyvaryors turnaj": "Flyvaryors",
            "Budějckej xtreme": "Budějckej", "Křupky na břehu": "Křupky",
            "Hanácké škvarek": "Hanácké", "Eager´s Cup": "Eager's Cup"}.get(name, name)


@cache
def processed() -> dict[str, pd.DataFrame]:
    return metrics.load_processed()


def read(rel: str) -> pd.DataFrame:
    return pd.read_csv(RP / rel)


# --- Season calendar / per competition day --------------------------------------------------

def competition_days() -> pd.DataFrame:
    """One row per WRFT competition day with the calendar fields (and Hungarian labels)."""
    d = read("phase4a/competition_days.csv").sort_values("date").reset_index(drop=True)
    d["event"] = d["competition"].map(short_competition)
    d["day_no"] = d.groupby("competition").cumcount() + 1
    d["weekday"] = d["date"].map(numbers.weekday_hu)
    d["below_peers"] = (d["peer_gap_win_rate_p_holm"] < 0.05) & (d["peer_gap_win_rate"] < 0)
    d["comp_day_id"] = _comp_day_ids(d)
    return d


def _comp_day_ids(d: pd.DataFrame) -> list[str]:
    days = pd.read_csv(config.PROCESSED / "weather_day.csv")[["competition", "date", "comp_day_id"]]
    first = days.drop_duplicates(["competition", "date"]).set_index(["competition", "date"])["comp_day_id"]
    return [first.get((c, dt), "") for c, dt in zip(d["competition"], d["date"])]


# --- Day 1 vs day 2 -------------------------------------------------------------------------

def day_pairs() -> pd.DataFrame:
    """Clean-heat rate per WRFT team, event and day (day_index 0/1 = day 1/2), for events with both days raced."""
    t = processed()
    h = t["heats"]
    h = h[h["is_wrft"] & h["win_value"].notna()]
    g = h.groupby(["competition", "team", "day_index"]).agg(heats=("clean_heat", "size"),
                                                            clean=("clean_heat", "mean")).reset_index()
    wide = g.pivot_table(index=["competition", "team"], columns="day_index", values=["clean", "heats"])
    wide.columns = [f"{a}_{b + 1}" for a, b in wide.columns]       # day_index 0/1 -> day 1/2
    wide = wide.dropna(subset=["clean_1", "clean_2"]).reset_index()
    wide["team_short"] = wide["team"].map(short_team)
    wide["event"] = wide["competition"].map(short_competition)
    return wide


def day_totals() -> pd.DataFrame:
    """Pooled clean-heat rate on day 1 and day 2: WRFT and the rest of the field (raw shares)."""
    h = processed()["heats"]
    h = h[h["win_value"].notna()]
    h = h.assign(group=h["is_wrft"].map({True: "WRFT", False: "field"}))
    out = h.groupby(["group", "day_index"])["clean_heat"].agg(["mean", "size"]).reset_index()
    out["day"] = out["day_index"] + 1
    return out


# --- One real heat, for the heat-strip timeline -------------------------------------------------

def heat_pair(competition_prefix: str = "Hanácké", team: str = "hopefuls", excel_row: int = 11) -> pd.DataFrame:
    """Both rows of one heat: the WRFT team's and its opponent's, with the eight time cells."""
    h = pd.read_parquet(config.PROCESSED / "heats.parquet")
    own = h[h["competition"].str.startswith(competition_prefix) & h["team_norm"].str.contains(team)
            & (h["excel_row"] == excel_row)]
    if len(own) != 1:
        raise ValueError(f"expected one heat row, found {len(own)}")
    pair = h[h["heat_id"] == own["heat_id"].iat[0]]
    return pair.sort_values("is_wrft", ascending=False).reset_index(drop=True)


# --- Impact ledger, in Hungarian groups --------------------------------------------------------

LEDGER_ROWS = [  # (lever_id in impact_ledger.csv or a fixed zero, Hungarian label, group)
    ("ceiling", "Ha egyáltalán nem hibáznánk (felső határ)", "Viszonyítás"),
    ("lineup_reorder|all", "Jobb futási sorrend, ugyanazokkal a kutyákkal", "Azonnal, ingyen"),
    ("day2", "Szombaton is annyi hibátlan futam, mint vasárnap", "Ki kell deríteni"),
    ("gap_club|all", "Hibák leszorítása a divízió szintjére", "Edzéssel"),
    ("gap_club|own_false_start", "   ebből: korai rajtok", "Edzéssel"),
    ("gap_club|own_pass_fault", "   ebből: korai váltások", "Edzéssel"),
    ("gap_club|own_run_fault", "   ebből: futási hibák", "Edzéssel"),
    ("lineup_swap|hopefuls", "Pax beállítása a Hopefulsba", "Kutyán múlik"),
    ("lineup_swap|zephyr", "Pax beállítása a Zephyrbe (optimista)", "Kutyán múlik"),
    ("heat", "Melegben is teljes tempó (felső becslés)", "A kutyák jólléte"),
    ("zero:lane", "A pálya színe (piros vagy kék)", "Nem számít"),
    ("zero:partner", "A váltótárs neme, ivarállapota", "Nem számít"),
]

LEVER_STRIP = {  # the "you are here" strip: lever_id -> short label
    "lineup_reorder|all": "Sorrend",
    "day2": "Szombat",
    "gap_club|all": "Hibák",
    "lineup_swap|hopefuls": "Pax",
    "heat": "Hőség",
}


def ledger() -> pd.DataFrame:
    """The ledger rows the deck shows, in display order, with Hungarian labels and groups."""
    led = read("phase5/impact_ledger.csv").set_index("lever_id")
    rows = []
    for lever_id, label, group in LEDGER_ROWS:
        if lever_id.startswith("zero:"):
            rows.append({"lever_id": lever_id, "label": label, "group": group,
                         "extra_wins": 0.0, "ci_low": 0.0, "ci_high": 0.0})
        else:
            r = led.loc[lever_id]
            rows.append({"lever_id": lever_id, "label": label, "group": group, "extra_wins": r["extra_wins"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"], "lever_en": r["lever"]})
    return pd.DataFrame(rows)


# --- Line-ups --------------------------------------------------------------------------------

def team_lineups() -> pd.DataFrame:
    """Current vs recommended order per WRFT team, with the expected gain and the ledger's extra wins."""
    t = read("phase4b/lineup_teams.csv")
    led = read("phase5/impact_ledger.csv").set_index("lever_id")
    t["team_short"] = t["team"].map(short_team)
    t["extra_wins"] = [led["extra_wins"].get(f"lineup_reorder|{s.lower()}", float("nan")) for s in t["team_short"]]
    t["ci_low"] = [led["ci_low"].get(f"lineup_reorder|{s.lower()}", float("nan")) for s in t["team_short"]]
    t["ci_high"] = [led["ci_high"].get(f"lineup_reorder|{s.lower()}", float("nan")) for s in t["team_short"]]
    t["order"] = t["team_short"].map({n: i for i, n in enumerate(TEAM_ORDER)})
    return t.sort_values("gain_from_order_s", ascending=False).reset_index(drop=True)


def dog_profiles() -> pd.DataFrame:
    return read("phase4b/dog_profiles.csv")


def scorecards() -> pd.DataFrame:
    return read("dog_scorecards.csv")


CATEGORY_HU = {"neutered male": "ivartalan kan", "neutered female": "ivartalan szuka",
               "intact male": "ivaros kan", "intact female": "ivaros szuka"}


# --- Everything the deck charts need, in one dict ------------------------------------------------

QUADRANT_NAMES = ["Scotty", "Ted", "Moon", "Bree", "Cookies", "Rex", "Sunny", "Negro"]   # training targets (findings F3-F4)


def lineup_breakdown_rows() -> pd.DataFrame:
    """The A-team plus each team's current and reordered line-up, with Hungarian labels."""
    c = read("phase4b/lineup_comparison.csv")
    keep = c["label"].str.startswith(("A-team", "Hopefuls", "Zephyr", "XXL", "Maximini"))
    c = c[keep].copy()
    c["label"] = (c["label"].str.replace("A-team", "Legjobb négyes", regex=False)
                  .str.replace(" now:", " most:", regex=False)
                  .str.replace(" reordered:", " új sorrend:", regex=False)
                  .str.replace(" > ", " › ", regex=False))
    return c


def chart_inputs() -> dict:
    k = numbers.key_numbers()
    days = competition_days()
    return {
        "days": days,
        "field_clean": k["field_clean_heat_rate"]["value"],
        "heat_pair": heat_pair(),
        "win_by_fault": read("phase3/win_by_fault_status.csv"),
        "win_by_gap": read("phase3/win_by_speed_gap.csv"),
        "ledger": ledger(),
        "day_pairs": day_pairs(),
        "day_totals": day_totals(),
        "cards": scorecards(),
        "quadrant_names": QUADRANT_NAMES,
        "pass_window": read("phase3/pass_window.csv"),
        "stability": read("phase4b/lineup_stability_dogs.csv"),
        "a_team": k["a_team"]["value"].split(" > "),
        "height": read("phase4b/lineup_height_dog.csv"),
        "breakdown": lineup_breakdown_rows(),
        "lane_dogs": read("phase4a/lane_wrft_dogs.csv"),
        "lane_days": read("phase4a/lane_by_ring_day.csv"),
        "lane_overall": read("phase4a/lane_run_effect.csv"),
        "lane_margin": numbers.value("lane_margin_s"),
        "partner": read("phase4a/partner_contrasts.csv"),
        "weather_curve": read("phase4b/weather_curve.csv"),
        "weather_pdp": read("phase4b/weather_gbm_pdp.csv"),
        "hinge": numbers.value("temp_hinge_c"),
        "weather_effects": read("phase4b/weather_effects.csv"),
        "weather_days": read("phase4b/weather_days.csv"),
        "dog_comp": read("phase4a/dog_by_competition.csv"),
        "heat_model": read("phase3/heat_win_model.csv"),
        "attribution": read("phase3/fault_attribution.csv"),
        "peer": read("phase3/peer_benchmark.csv"),
        "backtest_heats": read("phase4b/lineup_backtest_heats.csv"),
    }
