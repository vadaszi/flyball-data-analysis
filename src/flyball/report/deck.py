"""The Hungarian deck: slide text (text_hu.toml) + charts + tables -> HTML -> PDF (headless Chromium).

- `load_text()` reads the slide text and resolves every number placeholder;
- `providers` turn report tables into the cards and tables some slide layouts show;
- `render_html()` fills the Jinja2 templates; `to_pdf()` prints the HTML with Playwright.

Run through `scripts/run_phase6_presentation.py`.
"""

import os
import re
import tomllib
from pathlib import Path

import jinja2
import pandas as pd

from flyball import config
from flyball.report import figdata, numbers
from flyball.report.numbers import num, pct, render, sec

HERE = Path(__file__).resolve().parent
TEXT = HERE / "text_hu.toml"
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"

# Headless Chromium on this machine needs three libraries installed without root (see ANALYSIS_LOG 7.1).
CHROMIUM_LIBS = Path.home() / ".local" / "share" / "chromium-deps" / "root" / "usr" / "lib" / "x86_64-linux-gnu"

FIGURE_KEYS = ("figure", "figure2")
TEXT_FIELDS = ("title", "lead", "kicker", "caption", "caption2", "notes")


# --- Text ----------------------------------------------------------------------------------------

def raw_text() -> dict:
    return tomllib.loads(TEXT.read_text(encoding="utf-8"))


def _resolve(obj):
    if isinstance(obj, str):
        return render(obj)
    if isinstance(obj, list):
        return [_resolve(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("id", "layout", "part", "data", "strip", "figure", "figure2", "time", "status", "tag")
                    else _resolve(v)) for k, v in obj.items()}
    return obj


def load_text() -> dict:
    """The slide text with every {placeholder} replaced by its Hungarian-formatted number."""
    return _resolve(raw_text())


# --- Providers: cards and tables -----------------------------------------------------------------

def _order(s: str) -> list[str]:
    return s.split(" > ")


def team_lineups() -> dict:
    t = figdata.team_lineups()
    teams = []
    for r in t.itertuples():
        if r.gain_from_order_s < 0.3:
            continue
        now, best = _order(r.current_order), _order(r.best_order)
        teams.append({
            "team": r.team_short, "now": now, "best": best,
            "moved": [d for i, d in enumerate(best) if now[i] != d],
            "starter_changed": now[0] != best[0],
            "gain": sec(r.gain_from_order_s, 2),
            "wins": "+" + num(r.extra_wins, 1), "ci": f"{num(r.ci_low, 1)}–{num(r.ci_high, 1)}",
            "p_clean_now": pct(r.current_p_clean, 0),
        })
    optimal = [r.team_short for r in t.itertuples() if r.gain_from_order_s < 0.3]
    return {"teams": teams, "optimal": optimal}


FAULT_HU = {"false_start_rate": "korai rajt", "pass_fault_rate": "korai váltás", "run_fault_rate": "futási hiba",
            "own_false_start": "korai rajt", "own_pass_fault": "korai váltás", "own_run_fault": "futási hiba"}

HABITS = [  # team, peer metric, ledger fault, dogs, the dogs' scorecard column
    ("WildRunners XXL", "false_start_rate", "own_false_start", ["Scotty", "Negro", "Rex"], "false_start_rate"),
    ("WildRunners Zephyr", "run_fault_rate", "own_run_fault", ["Ted"], "run_fault_rate"),
    ("WildRunners hopefuls", "pass_fault_rate", "own_pass_fault", ["Moon", "Maggie"], "early_pass_rate"),
    ("WildRunners Maximini", "pass_fault_rate", "own_pass_fault", ["Bree", "Bella"], "early_pass_rate"),
]


def fault_habits() -> dict:
    peer = figdata.read("phase3/peer_benchmark.csv").set_index(["team", "metric"])
    led = figdata.read("phase5/impact_ledger.csv").set_index("lever_id")
    cards = figdata.scorecards().set_index("dog")
    rows = []
    for team, metric, fault, dogs, col in HABITS:
        p = peer.loc[(team, metric)]
        short = figdata.short_team(team)
        lv = led.loc[f"gap|{short.lower()}|{fault}"]
        sig = p["p_holm"] < 0.05
        rows.append([short, f"{FAULT_HU[metric]} {numbers.pp(p['estimate'])}" + ("" if sig else " (lehet véletlen is)"),
                     ", ".join(f"{d} {pct(cards.loc[d, col], 0)}" for d in dogs),
                     f"+{num(lv['extra_wins'], 1)}"])
    return {"columns": ["Csapat", "Lemaradás a divízióhoz képest", "Érintett kutyák (hibaarány)", "Plusz győzelem"],
            "rows": rows, "align": ["l", "l", "l", "r"]}


def a_team() -> dict:
    prof = figdata.dog_profiles().set_index("dog")
    dogs = numbers.value("a_team").split(" > ")
    tiles = []
    for i, d in enumerate(dogs):
        p = prof.loc[d]
        if i == 0:
            role, line = "rajtoló", f"rajt {sec(p['start_s'], 2)} · korai rajt {pct(p['false_start_p'], 0)}"
        else:
            role, line = f"{i + 1}. kutya", f"váltás {sec(p['pass_s'], 2)} · korai váltás {pct(p['early_pass_p'], 0)}"
        tiles.append({"dog": d, "role": role, "run": sec(p["run_25cm_s"], 2), "line": line,
                      "height": num(p["height_cm"], 1).replace(",0", "") + " cm",
                      "run_fault": pct(p["run_fault_p"], 1)})
    comp = figdata.read("phase4b/lineup_comparison.csv")
    hurdle = comp.loc[comp["label"].str.startswith("A-team"), "hurdle_cm"].iat[0]
    return {"tiles": tiles, "hurdle": num(hurdle, 1).replace(",0", "") + " cm"}


def reserves() -> dict:
    r = figdata.read("phase4b/lineup_reserves.csv")
    rows = [[x.reserve, x.replaces, x.line_up.replace(" > ", " › "), sec(x.expected_s, 2), "+" + sec(x.cost_vs_a_team_s, 2)]
            for x in r.itertuples()]
    return {"columns": ["Tartalék", "Kit vált", "Összeállítás", "Várható idő", "Különbség"], "rows": rows,
            "align": ["l", "l", "l", "r", "r"]}


def _lever_hu(lever_id: str, lever: str) -> str:
    parts = lever_id.split("|")
    if lever_id == "ceiling":
        return "Ha egyáltalán nem hibáznánk (felső határ)"
    if lever_id == "day2":
        return "Szombaton is annyi hibátlan futam, mint vasárnap"
    if lever_id == "heat":
        return "Melegben is teljes tempó (felső becslés)"
    if lever_id == "lineup_reorder|all":
        return "Minden csapat a javasolt sorrendben fut"
    if parts[0] == "gap_club":
        return "Minden csapat: " + ("minden hibatípus a divízió szintjére" if parts[1] == "all" else
                                    FAULT_HU[parts[1]] + " a divízió szintjére")
    team = figdata.short_team(parts[1])
    if parts[0] == "gap":
        return f"{team}: {FAULT_HU[parts[2]]} a divízió szintjére"
    new = lever.split("->")[-1].strip().replace(" > ", " › ")
    if parts[0] == "lineup_reorder":
        return f"{team}: új sorrend ({new})"
    if parts[0] == "lineup_swap":
        return f"{team}: cserekutyával ({new})"
    return lever


GROUP_HU = {"reference": "viszonyítás", "line-up: bench swap": "cserekutya", "second-day effect": "szombati nap",
            "line-up: reorder (club)": "sorrend", "line-up: reorder": "sorrend",
            "fault gap to division peers (club)": "hibák", "fault gap to division peers": "hibák",
            "weather": "időjárás"}


def ledger_table(min_wins: float = 5.0) -> dict:
    led = figdata.read("phase5/impact_ledger.csv")
    led = led[led["extra_wins"] >= min_wins]
    rows = [[_lever_hu(r.lever_id, r.lever), GROUP_HU.get(r.group, r.group),
             f"+{num(r.extra_wins, 1)}", f"{num(r.ci_low, 1)}–{num(r.ci_high, 1)}", numbers.num(r.club_win_rate_pp, 1, True)]
            for r in led.itertuples()]
    return {"columns": ["Lehetőség", "Típus", "Plusz győzelem", "Bizonytalansági tartomány", "Győzelmi arány változása (százalékpont)"],
            "rows": rows, "align": ["l", "l", "r", "r", "r"], "small": True}


def team_table() -> dict:
    t = figdata.read("phase3/team_summary.csv")
    t["label"] = t["team"].map(lambda s: "Mezőny (nem WRFT)" if s.startswith("Field") else
                               ("WRFT összesen" if s.startswith("WRFT") else figdata.short_team(s)))
    rows = [[r.label, num(r.heats, 0), pct(r.win_rate, 0), pct(r.clean_heat_rate, 0), num(r.median_clean_time, 2),
             pct(r.false_start_rate, 0), pct(r.heat_pass_fault_rate, 0), pct(r.heat_run_fault_rate, 0),
             num(r.median_start, 2), num(r.median_pass, 2), num(r.median_run, 2)] for r in t.itertuples()]
    return {"columns": ["Csapat", "Futam", "Győzelem", "Hibátlan futam", "Jellemző tiszta idő (mp)", "Korai rajtos futam",
                        "Korai váltásos futam", "Futási hibás futam", "Jellemző rajt (mp)", "Jellemző váltás (mp)",
                        "Jellemző futás (mp)"],
            "rows": rows, "align": ["l"] + ["r"] * 10, "emphasis_last": 2}


def _dog_rows(cards: pd.DataFrame) -> list[list[str]]:
    rows = []
    for r in cards.itertuples():
        rows.append([r.dog, figdata.CATEGORY_HU.get(r.category, r.category), num(r.valid_runs, 0),
                     num(r.median_run, 2), num(r.adj_run_s, 2), num(r.usual_hurdle_cm, 1).replace(",0", ""),
                     num(r.starts, 0), pct(r.false_start_eb, 0) if r.starts else "–",
                     num(r.passes, 0), pct(r.early_pass_eb, 0) if r.passes else "–", pct(r.run_fault_eb, 1)])
    return rows


DOG_COLUMNS = ["Kutya", "Nem, ivarállapot", "Futás", "Jellemző futás (mp)", "Összevethető futás (mp)", "Akadály (cm)",
               "Rajt", "Korai rajt*", "Váltás", "Korai váltás*", "Futási hiba*"]


def _dog_table(part: int) -> dict:
    c = figdata.scorecards()
    c = c[c["valid_runs"] >= numbers.value("pool_min_runs")].sort_values("adj_run_s").reset_index(drop=True)
    half = (len(c) + 1) // 2
    c = c.iloc[:half] if part == 1 else c.iloc[half:]
    return {"columns": DOG_COLUMNS, "rows": _dog_rows(c), "align": ["l", "l"] + ["r"] * 9, "small": True,
            "footnote": "* Korrigált arány: kevés próbálkozásnál a csoportátlag felé igazítva, hogy egy-két véletlen hiba ne "
                        "torzítson. Összevethető futás: a kutya becsült futási ideje 25 cm-es akadályon, első helyen futva."}


def dog_table_1() -> dict:
    return _dog_table(1)


def dog_table_2() -> dict:
    return _dog_table(2)


def partner_table() -> dict:
    t = figdata.read("phase4a/partner_table.csv")
    rows = [[figdata.CATEGORY_HU[r.incoming_category], num(r.passes, 0), num(r.incoming_dogs, 0),
             num(r.incoming_age_median_y, 1), num(r.median_pass_s, 2), pct(r.ok_share, 0), pct(r.early_pass_rate, 1),
             pct(r.held_pass_rate, 1), num(r.outgoing_median_run_s, 2)] for r in t.itertuples()]
    return {"columns": ["Beérkező kutya", "Váltás", "Kutya", "Jellemző kor (év)", "Jellemző váltás (mp)", "„ok” váltás",
                        "Korai váltás", "Visszatartott váltás", "A kifutó kutya jellemző futása (mp)"],
            "rows": rows, "align": ["l"] + ["r"] * 8}


def _days_table(part: int) -> dict:
    d = figdata.competition_days()
    d = d.iloc[:10] if part == 1 else d.iloc[10:]
    rows = []
    for r in d.itertuples():
        rows.append([pd.Timestamp(r.date).strftime("%m.%d."), r.event + (" ▲" if r.below_peers else ""),
                     r.weekday[:3], num(r.heats, 0), pct(r.win_rate, 0), pct(r.clean_heat_rate, 0),
                     pct(r.false_start_rate, 0), pct(r.heat_pass_fault_rate, 0), pct(r.heat_run_fault_rate, 0),
                     pct(r.share_losses_avoidable, 0), num(r.speed_index_wrft_pct, 1, True) + "%",
                     num(r.temp_mean_c, 0) + " °C", num(r.wind_mean_ms, 1), num(r.precip_total_mm, 1)])
    return {"columns": ["Dátum", "Verseny", "Nap", "Futam", "Győzelem", "Hibátlan", "Korai rajt", "Korai váltás",
                        "Futási hiba", "Elkerülhető vereség", "Sebesség (WRFT)", "Hőm.", "Szél (m/s)", "Eső (mm)"],
            "rows": rows, "align": ["l", "l", "l"] + ["r"] * 11, "small": True,
            "footnote": "Hibák: a futamok hány százalékában fordultak elő. Elkerülhető vereség: a vereségek arányában. "
                        "Sebesség: ugyanazok a kutyák a saját átlagos napjukhoz képest (− = gyorsabb). ▲: kevesebb győzelem, "
                        "mint a divízió többi csapatáé."}


def days_table_1() -> dict:
    return _days_table(1)


def days_table_2() -> dict:
    return _days_table(2)


PROVIDERS = {f.__name__: f for f in (team_lineups, fault_habits, a_team, reserves, ledger_table, team_table,
                                     dog_table_1, dog_table_2, partner_table, days_table_1, days_table_2)}


# --- HTML and PDF ------------------------------------------------------------------------------

def environment() -> jinja2.Environment:
    return jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=True,
                              trim_blocks=True, lstrip_blocks=True)


def slides(text: dict) -> list[dict]:
    """Slides with their number, data and figure paths attached."""
    out = []
    main = [s for s in text["slide"] if s["part"] == "main"]
    for i, s in enumerate(text["slide"], start=1):
        s = dict(s)
        s["no"] = i
        if s.get("data"):
            s["table"] = PROVIDERS[s["data"]]()
        s["main_total"] = len(main)
        out.append(s)
    return out


def render_html(text: dict, fig_dir: Path, static_dir: Path) -> str:
    """The whole deck as one HTML document (figures and fonts referenced by file URI)."""
    tpl = environment().get_template("deck.html.j2")
    strip_name = {k: "strip_" + k.split("|")[0] for k in figdata.LEVER_STRIP}
    return tpl.render(meta=text["meta"], slides=slides(text), glossary=text["glossary"], legend=text["legend"],
                      fig=lambda name: (fig_dir / f"{name}.svg").as_uri(), strip_name=strip_name,
                      static=static_dir.as_uri())


def render_notes(text: dict) -> str:
    tpl = environment().get_template("notes.html.j2")
    return tpl.render(meta=text["meta"], slides=slides(text), static=STATIC.as_uri())


def _browser_env() -> dict:
    env = dict(os.environ)
    if CHROMIUM_LIBS.exists():
        env["LD_LIBRARY_PATH"] = f"{CHROMIUM_LIBS}:{env.get('LD_LIBRARY_PATH', '')}".rstrip(":")
    return env


def _in_thread(fn):
    """Run a Playwright job in a worker thread: its sync API refuses to run inside an event loop (Jupyter)."""
    from concurrent.futures import ThreadPoolExecutor

    def wrapper(*args, **kwargs):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(fn, *args, **kwargs).result()
    return wrapper


@_in_thread
def to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Print an HTML file to PDF with headless Chromium (CSS @page decides the page size)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(env=_browser_env())
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(path=str(pdf_path), print_background=True, prefer_css_page_size=True)
        browser.close()
    _strip_pdf_dates(pdf_path)


def _strip_pdf_dates(pdf_path: Path) -> None:
    """Chromium stamps creation dates into the PDF; blank them so rebuilds are byte-identical."""
    data = pdf_path.read_bytes()
    data = re.sub(rb"/(CreationDate|ModDate) \(D:[0-9+\-Z']+\)", lambda m: b"/" + m.group(1) + b" (D:20260101000000Z)", data)
    pdf_path.write_bytes(data)


@_in_thread
def screenshots(html_path: Path, out_dir: Path, width: int = 1280, height: int = 720) -> list[Path]:
    """One PNG per slide, for visual checks (not part of the deliverable)."""
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(env=_browser_env())
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        for i, el in enumerate(page.locator("section.slide").all(), start=1):
            path = out_dir / f"slide_{i:02d}.png"
            el.screenshot(path=str(path))
            paths.append(path)
        browser.close()
    return paths


def build(out_dir: Path, fig_dir: Path | None = None) -> dict[str, Path]:
    """Write deck.html, the deck PDF and the speaker-notes PDF into `out_dir`."""
    fig_dir = fig_dir or config.FIGURES / "phase6"
    text = load_text()
    build_dir = config.REPORTS / "phase6"
    build_dir.mkdir(parents=True, exist_ok=True)
    html = build_dir / "deck.html"
    html.write_text(render_html(text, fig_dir, STATIC), encoding="utf-8")
    notes = build_dir / "notes.html"
    notes.write_text(render_notes(text), encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / text["meta"]["pdf_name"]
    notes_pdf = out_dir / text["meta"]["notes_name"]
    to_pdf(html, pdf)
    to_pdf(notes, notes_pdf)
    return {"html": html, "pdf": pdf, "notes_pdf": notes_pdf}
