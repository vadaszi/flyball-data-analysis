"""The Hungarian interactive website: one static folder (`prezentacio/`) that works offline.

- `index.html` is rendered from `templates/site.html.j2` with the same text as the deck;
- the data behind the interactive parts goes into `assets/data.js` (a script, not JSON, so the
  page also works when opened straight from disk, where browsers block fetch());
- the line-up builder re-implements `lineup.score_orders` in `assets/site.js`; `lineup_model()`
  exports exactly the arrays the Python search used, and the tests check both agree;
- charts that need no interaction are the deck's SVGs, copied to `assets/img/`;
- `adatok/` holds downloadable CSVs with Hungarian headers.
"""

import json
import shutil
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from flyball import config, lineup, metrics
from flyball.report import deck, figdata, numbers
from flyball.report.numbers import num, pct

STATIC = deck.STATIC
SITE_STATIC = deck.TEMPLATES / "site"
VENDOR = ["vega.min.js", "vega-lite.min.js", "vega-embed.min.js"]


# --- Line-up builder model -----------------------------------------------------------------------

def profiles() -> pd.DataFrame:
    """The Phase 4B dog profiles, recomputed so the speed model's terms are attached (attrs)."""
    t = metrics.load_processed()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # MixedLM convergence chatter
        return lineup.dog_profiles(t["runs"], t["dogs"], t["hurdle_check"])


def lineup_model(prof: pd.DataFrame) -> dict:
    """Per-dog arrays for the pool dogs, as `lineup._arrays` builds them, plus the fault cost."""
    pool = prof[prof["in_pool"]].reset_index(drop=True)
    a = lineup._arrays(pool)
    cards = figdata.scorecards().set_index("dog")
    dogs = []
    for i, name in enumerate(a["dogs"]):
        dogs.append({
            "name": str(name),
            "run": np.round(a["run"][i], 5).tolist(),                 # [height index][position 1-4]
            "start": None if np.isinf(a["start"][i]) else round(float(pool.loc[i, "start_s"]), 5),
            "start_any": round(float(pool.loc[i, "start_s"]), 5),
            "pass": round(float(a["pass"][i]), 5), "fs": round(float(a["fs"][i]), 5),
            "ep": round(float(a["ep"][i]), 5), "rf": round(float(a["rf"][i]), 5), "h": int(a["h_idx"][i]),
            "height": float(pool.loc[i, "height_cm"]), "starts": int(pool.loc[i, "starts"]),
            "category": figdata.CATEGORY_HU.get(cards.loc[name, "category"], "") if name in cards.index else "",
        })
    cost = float(pd.read_csv(config.REPORTS / "phase4b" / "lineup_meta.csv")["fault_cost_s"].iat[0])
    return {"heights": lineup.HEIGHTS.tolist(), "fault_cost": cost, "dogs": dogs}


def lineup_presets() -> list[dict]:
    """The A-team and every team's current and recommended order, for the builder's preset menu."""
    out = [{"label": "A legjobb négyes", "dogs": numbers.value("a_team").split(" > ")}]
    for r in figdata.team_lineups().sort_values("order").itertuples():
        out.append({"label": f"{r.team_short} – most", "dogs": r.current_order.split(" > ")})
        if r.gain_from_order_s >= 0.01:
            out.append({"label": f"{r.team_short} – javasolt sorrendben", "dogs": r.best_order.split(" > ")})
    return out


# --- Data for the page ----------------------------------------------------------------------------

def _clean(obj):
    """JSON-safe: NaN -> None, numpy scalars -> Python."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if np.isnan(obj) else round(float(obj), 5)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def team_days() -> pd.DataFrame:
    """Every WRFT team's results on every competition day (for the day explorer)."""
    t = figdata.processed()
    h, r = t["heats"], t["runs"]
    out = metrics.team_summary(h[h["is_wrft"]], r[r["is_wrft"]], group=["date", "team"])
    out["team_short"] = out["team"].map(figdata.short_team)
    return out


def day_records() -> list[dict]:
    days = figdata.competition_days()
    teams = team_days()
    recs = []
    for d in days.itertuples():
        tt = teams[teams["date"] == d.date].sort_values("team_short")
        recs.append({
            "id": d.comp_day_id, "date": d.date, "date_hu": numbers.date_hu(d.date), "event": d.event,
            "competition": d.competition, "venue": d.venue, "weekday": d.weekday, "heats": d.heats,
            "win": d.win_rate, "win_lo": d.win_ci_low, "win_hi": d.win_ci_high, "clean": d.clean_heat_rate,
            "fs": d.false_start_rate, "pf": d.heat_pass_fault_rate, "rf": d.heat_run_fault_rate,
            "avoidable": d.share_losses_avoidable, "losses": d.losses, "below": bool(d.below_peers),
            "peer_win_gap": d.peer_gap_win_rate, "speed_wrft": d.speed_index_wrft_pct,
            "speed_field": d.speed_index_field_pct, "temp": d.temp_mean_c, "temp_max": d.temp_max_c,
            "humidity": d.humidity_mean_pct, "wind": d.wind_mean_ms, "gust": d.gust_max_ms,
            "rain": d.precip_total_mm, "rain_before": d.precip_24h_before_mm,
            "teams": [{"team": x.team_short, "heats": x.heats, "win": x.win_rate, "clean": x.clean_heat_rate,
                       "clean_time": x.median_clean_time, "best": x.best_clean_time, "fs": x.false_start_rate,
                       "pf": x.heat_pass_fault_rate, "rf": x.heat_run_fault_rate, "run": x.median_run}
                      for x in tt.itertuples()],
        })
    return recs


def dog_records() -> list[dict]:
    c = figdata.scorecards()
    return [{"dog": r.dog, "category": figdata.CATEGORY_HU.get(r.category, r.category), "breed": BREED_HU.get(r.breed_group, r.breed_group),
             "runs": r.valid_runs, "competitions": r.competitions, "median_run": r.median_run,
             "adj_run": r.adj_run_s, "best_run": r.best_run_p05, "hurdle": r.usual_hurdle_cm,
             "position": r.usual_position, "starts": r.starts, "median_start": r.median_start,
             "fs": r.false_start_eb if r.starts else None, "passes": r.passes, "median_pass": r.median_pass,
             "ep": r.early_pass_eb if r.passes else None, "rf": r.run_fault_eb, "any": r.any_fault_eb,
             "teams": r.teams} for r in c.itertuples()]


def ledger_records() -> list[dict]:
    led = figdata.read("phase5/impact_ledger.csv")
    return [{"label": deck._lever_hu(r.lever_id, r.lever), "group": deck.GROUP_HU.get(r.group, r.group),
             "wins": r.extra_wins, "lo": r.ci_low, "hi": r.ci_high, "pp": r.club_win_rate_pp,
             "heats": r.heats_affected} for r in led.itertuples()]


def site_data(prof: pd.DataFrame) -> dict:
    main = figdata.ledger()
    return _clean({
        "ledger_main": [{"label": r.label.strip(), "group": r.group, "wins": r.extra_wins, "lo": r.ci_low,
                         "hi": r.ci_high, "sub": r.label.startswith("   ")} for r in main.itertuples()],
        "ledger_all": ledger_records(),
        "days": day_records(),
        "field_clean": numbers.value("field_clean_heat_rate"),
        "dogs": dog_records(),
        "quadrant_targets": figdata.QUADRANT_NAMES,
        "pool_min_runs": numbers.value("pool_min_runs"),
        "a_team": numbers.value("a_team").split(" > "),
        "model": lineup_model(prof),
        "presets": lineup_presets(),
    })


# --- CSV downloads -------------------------------------------------------------------------------

BREED_HU = {"Border Collie": "border collie", "Mix": "keverék", "Other": "más fajta"}

# Downloadable tables: Hungarian column names, decimal comma and semicolons (what Hungarian Excel expects).
DOG_CSV = {"dog": "kutya", "category": "nem_es_ivarallapot", "breed_group": "fajta", "valid_runs": "ertekelheto_futas",
           "competitions": "verseny", "median_run": "jellemzo_futas_mp", "adj_run_s": "osszevetheto_futas_mp",
           "usual_hurdle_cm": "akadaly_cm", "starts": "rajt", "false_starts": "korai_rajt_db",
           "false_start_eb": "korai_rajt_arany_korrigalt", "passes": "valtas", "early_passes": "korai_valtas_db",
           "early_pass_eb": "korai_valtas_arany_korrigalt", "median_pass": "jellemzo_valtas_mp",
           "runs_attempted": "futas", "run_faults": "futasi_hiba_db", "run_fault_eb": "futasi_hiba_arany_korrigalt"}
DAY_CSV = {"date": "datum", "competition": "verseny", "venue": "helyszin", "weekday": "nap", "teams": "wrft_csapatok",
           "heats": "futam", "win_rate": "gyozelem_arany", "clean_heat_rate": "hibatlan_futam_arany",
           "median_clean_time": "jellemzo_tiszta_ido_mp", "best_clean_time": "legjobb_tiszta_ido_mp",
           "false_start_rate": "korai_rajtos_futam_arany", "heat_pass_fault_rate": "korai_valtasos_futam_arany",
           "heat_run_fault_rate": "futasi_hibas_futam_arany", "losses": "vereseg",
           "avoidable_losses": "elkerulheto_vereseg", "below_peers": "divizio_alatt",
           "speed_index_wrft_pct": "sebesseg_wrft_szazalek", "temp_mean_c": "atlaghomerseklet_c",
           "temp_max_c": "max_homerseklet_c", "humidity_mean_pct": "paratartalom_szazalek", "wind_mean_ms": "szel_ms",
           "gust_max_ms": "szellokes_ms", "precip_total_mm": "eso_mm", "precip_24h_before_mm": "eso_elozo_24_ora_mm"}
TEAM_DAY_CSV = {"date": "datum", "team_short": "csapat", "heats": "futam", "win_rate": "gyozelem_arany",
                "clean_heat_rate": "hibatlan_futam_arany", "median_clean_time": "jellemzo_tiszta_ido_mp",
                "best_clean_time": "legjobb_tiszta_ido_mp", "false_start_rate": "korai_rajtos_futam_arany",
                "heat_pass_fault_rate": "korai_valtasos_futam_arany", "heat_run_fault_rate": "futasi_hibas_futam_arany",
                "median_start": "jellemzo_rajt_mp", "median_pass": "jellemzo_valtas_mp", "median_run": "jellemzo_futas_mp"}


def _to_csv(df: pd.DataFrame, path: Path) -> Path:
    df.to_csv(path, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    return path


def write_csvs(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    cards = figdata.scorecards()
    cards = cards.assign(category=cards["category"].map(figdata.CATEGORY_HU), breed_group=cards["breed_group"].map(BREED_HU))
    days = figdata.competition_days()
    days = days.assign(below_peers=days["below_peers"].map({True: "igen", False: "nem"}))
    teams = team_days()
    teams = teams.assign(date=pd.to_datetime(teams["date"]).dt.strftime("%Y-%m-%d")).merge(
        days[["date", "competition"]], on="date", how="left")
    led = pd.DataFrame(ledger_records()).rename(columns={"label": "lehetoseg", "group": "tipus", "wins": "plusz_gyozelem",
                                                         "lo": "also_hatar", "hi": "felso_hatar",
                                                         "pp": "gyozelmi_arany_valtozasa_szazalekpont",
                                                         "heats": "erintett_futamok"})
    return [
        _to_csv(cards[list(DOG_CSV)].rename(columns=DOG_CSV), folder / "kutya_adatlapok.csv"),
        _to_csv(days[list(DAY_CSV)].rename(columns=DAY_CSV), folder / "versenynapok.csv"),
        _to_csv(teams[["competition", *TEAM_DAY_CSV]].rename(columns={"competition": "verseny", **TEAM_DAY_CSV}),
                folder / "csapat_versenynapok.csv"),
        _to_csv(led, folder / "lehetosegek_rangsora.csv"),
    ]


# --- Build --------------------------------------------------------------------------------------------

def render_index(text: dict, data: dict) -> str:
    tpl = deck.environment().get_template("site.html.j2")
    by_id = {s["id"]: s for s in deck.slides(text)}
    k = numbers.key_numbers()
    return tpl.render(meta=text["meta"], site=text["site"], S=by_id, glossary=text["glossary"],
                      legend=text["legend"], k=k, num=num, pct=pct, dog_count=len(data["dogs"]),
                      days=data["days"])


def build(out_dir: Path, fig_dir: Path | None = None, prof: pd.DataFrame | None = None) -> dict[str, Path]:
    """Write index.html, assets/ and adatok/ into `out_dir` (the PDFs are written by deck.build)."""
    fig_dir = fig_dir or config.FIGURES / "phase6"
    prof = profiles() if prof is None else prof
    text = deck.load_text()
    assets = out_dir / "assets"
    for sub in ("img", "vendor", "fonts"):
        (assets / sub).mkdir(parents=True, exist_ok=True)
    for f in fig_dir.glob("*.svg"):
        shutil.copy2(f, assets / "img" / f.name)
    for v in VENDOR:
        shutil.copy2(STATIC / "vendor" / v, assets / "vendor" / v)
    for f in (STATIC / "fonts").iterdir():
        shutil.copy2(f, assets / "fonts" / f.name)
    for f in ("site.css", "site.js", "lineup.js"):
        shutil.copy2(SITE_STATIC / f, assets / f)
    data = site_data(prof)
    (assets / "data.js").write_text("window.WRFT = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                                    + ";\n", encoding="utf-8")
    index = out_dir / "index.html"
    index.write_text(render_index(text, data), encoding="utf-8")
    shutil.copy2(SITE_STATIC / "OLVASS_EL.md", out_dir / "OLVASS_EL.md")
    shutil.rmtree(out_dir / "adatok", ignore_errors=True)          # no stale downloads from earlier builds
    csvs = write_csvs(out_dir / "adatok")
    return {"index": index, "data": assets / "data.js", "csvs": csvs}
