"""Phase 6: Hungarian number formatting, the slide text, the line-up builder's JS port, and the folder's links."""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pandas as pd
import pytest

from flyball import config
from flyball.report import deck, numbers, site
from flyball.report.numbers import MINUS, NBSP, THIN

OUT = config.ROOT / "prezentacio"


# --- Formatting ---------------------------------------------------------------------------------

def test_hungarian_number_formats():
    assert numbers.num(4.28) == "4,28"
    assert numbers.num(-0.291, 2) == MINUS + "0,29"
    assert numbers.num(1116, 0) == f"1{THIN}116"
    assert numbers.num(0.0002, 3, sign=True) == "±0,000"
    assert numbers.pct(0.4077) == "40,8%"
    assert numbers.pp(0.16, 0) == f"+16{NBSP}százalékpont"
    assert numbers.sec(0.0064) == f"0,006{NBSP}mp"
    assert numbers.sec(4.28) == f"4,28{NBSP}mp"
    assert numbers.date_hu("2023-04-22") == "2023. ápr. 22."


def test_placeholders_with_modifiers_and_ci():
    assert numbers.render("{wrft_win_rate}") == "40,8%"
    assert numbers.render("{impact_all_reorders|ci}") == f"+27{NBSP}(20–33)"
    assert numbers.render("{day2_clean_heat_wrft|pp|nounit|nosign|d0} százalékponttal") == "16 százalékponttal"
    assert numbers.render("{weather_day_r2|as_pct}") == "77%"
    neg = numbers.render("{day2_false_start_wrft|pp|ci}")
    assert neg.startswith(MINUS + "10,0") and "…" in neg            # negative CI uses the ellipsis separator
    assert numbers.render("{dog.maggie.starts}") == "14"
    with pytest.raises(KeyError):
        numbers.render("{no_such_number}")


# --- Slide text ---------------------------------------------------------------------------------

def _strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")


NON_TEXT_KEYS = ("id", "time", "data", "strip", "figure", "figure2", "layout", "part", "status", "tag",
                 "pdf_name", "notes_name")
ALLOWED = re.compile(r"\b20\d\d\b|95%|\(\d/\d\)|„0”|reports/\S+|\b\d\.(?=\s|$)")    # years, CI level, page/ordinal marks


def test_every_placeholder_resolves_and_no_number_is_typed_in():
    text = deck.raw_text()
    for path, s in _strings(text):
        if path.rsplit(".", 1)[-1].split("[")[0] in NON_TEXT_KEYS:
            continue
        numbers.render(s)                                            # raises on an unknown key
        rest = ALLOWED.sub("", numbers.PLACEHOLDER.sub("", s))
        assert not re.search(r"\d", rest), f"hard-coded number in {path}: {s!r}"


def test_deck_has_main_part_and_appendix_and_all_figures_exist():
    text = deck.load_text()
    parts = [s["part"] for s in text["slide"]]
    assert parts.count("main") >= 12 and parts.count("appendix") >= 15
    figs = {s.get(k) for s in text["slide"] for k in ("figure", "figure2")} - {None}
    missing = [f for f in figs if not (config.FIGURES / "phase6" / f"{f}.svg").exists()]
    assert not missing, missing
    assert sum(t["layout"] == "summary" for t in text["slide"]) == 1


# --- Line-up builder: the exported arrays and the JS port agree with Python ---------------------------

@pytest.fixture(scope="module")
def model():
    return site.lineup_model(site.profiles())


def _score_py(model, names):
    """The JS formula, in Python, on the exported arrays."""
    by = {d["name"]: d for d in model["dogs"]}
    ds = [by[n] for n in names]
    h = min(d["h"] for d in ds)
    runs = sum(d["run"][h][i] for i, d in enumerate(ds))
    start = ds[0]["start"] if ds[0]["start"] is not None else ds[0]["start_any"]
    passes = sum(d["pass"] for d in ds[1:])
    nf = ds[0]["fs"] + sum(d["ep"] for d in ds[1:]) + sum(d["rf"] for d in ds)
    return start + runs + passes + model["fault_cost"] * nf


def _comparison():
    c = pd.read_csv(config.REPORTS / "phase4b" / "lineup_comparison.csv")
    return [(r.line_up.split(" > "), r.expected_s) for r in c.itertuples()]


def test_exported_model_reproduces_the_python_line_up_scores(model):
    for names, expected in _comparison():
        assert _score_py(model, names) == pytest.approx(expected, abs=2e-3), names


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_scorer_matches_python(model, tmp_path):
    (tmp_path / "model.json").write_text(json.dumps(model))
    cases = [names for names, _ in _comparison()]
    script = f"""
      require({json.dumps(str(deck.TEMPLATES / 'site' / 'lineup.js'))});
      const M = require({json.dumps(str(tmp_path / 'model.json'))});
      const L = globalThis.WRFTLineup.make(M);
      const cases = {json.dumps(cases)};
      console.log(JSON.stringify({{scores: cases.map(c => L.score(c).expected),
                                  best: L.bestOrder(["Enola", "Alfie", "Pax", "Maggie"])}}));
    """
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for (names, expected), js in zip(_comparison(), out["scores"]):
        assert js == pytest.approx(expected, abs=2e-3), names
    assert " > ".join(out["best"]) == numbers.value("a_team")      # the A-team's own order is its best order


# --- The upload folder -------------------------------------------------------------------------------

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v and not v.startswith(("#", "http", "mailto:")):
                self.refs.append(v)


@pytest.mark.skipif(not (OUT / "index.html").exists(), reason="run scripts/run_phase6_presentation.py first")
def test_every_link_in_the_website_points_into_the_folder():
    p = _Links()
    p.feed((OUT / "index.html").read_text(encoding="utf-8"))
    assert p.refs
    missing = [r for r in p.refs if not (OUT / r).exists()]
    assert not missing, missing
    assert any(r.endswith(".pdf") for r in p.refs)                  # the site links to the deck
