"""Unit tests for the cell-level parsing rules."""

import math
from datetime import date

import pandas as pd
import pytest

from flyball import dogs, parse


@pytest.mark.parametrize("value, slot, expected", [
    (4.2700000000000005, "run", (4.27, "number")),
    ("OK", "chg", (0.0, "ok")),
    ("Ok", "chg", (0.0, "ok")),
    ("chyba", "chg", (math.nan, "error")),
    ("error", "chg", (math.nan, "error")),
    ("mimo", "run", (math.nan, "outside")),
    ("outside", "run", (math.nan, "outside")),
    ("vběhl", "run", (math.nan, "run_in")),
    ("run in", "run", (math.nan, "run_in")),
    (-0.06, "start", (-0.06, "false_start")),
    (-0.19, "chg", (-0.19, "early_pass")),
    (-2.44, "run", (-2.44, "negative_run")),
    (None, "chg", (math.nan, "missing")),
    ("banana", "run", (math.nan, "unknown_text")),
])
def test_classify_time(value, slot, expected):
    seconds, code = parse.classify_time(value, slot)
    assert code == expected[1]
    assert (math.isnan(seconds) and math.isnan(expected[0])) or seconds == expected[0]


@pytest.mark.parametrize("title, competition, ring, venue, dates", [
    ("Hanácké škvarek (Heroltice) 2023. április 22-23.", "Hanácké škvarek", None, "Heroltice",
     [date(2023, 4, 22), date(2023, 4, 23)]),
    ("Eager´s Cup 2. ring (Žamberk) 2023. május 6-7.", "Eager´s Cup", 2, "Žamberk",
     [date(2023, 5, 6), date(2023, 5, 7)]),
    ("Máchale, spadlo ti to! (Louňovice) 2023. július 15-16.", "Máchale, spadlo ti to!", None,
     "Louňovice", [date(2023, 7, 15), date(2023, 7, 16)]),
    ("EFC - Ring 1 (Tápiószentmárton) 2023. július 29.", "EFC", 1, "Tápiószentmárton",
     [date(2023, 7, 29)]),
])
def test_parse_title(title, competition, ring, venue, dates):
    assert parse.parse_title(title) == {
        "competition": competition, "ring": ring, "venue": venue, "dates": dates}


def test_day_index_splits_at_single_drop():
    seconds = pd.Series([30000, 40000, 60000, 29000, 50000])
    assert parse.assign_day_index(seconds, 2).tolist() == [0, 0, 0, 1, 1]


def test_day_index_rejects_unexpected_drops():
    with pytest.raises(ValueError):
        parse.assign_day_index(pd.Series([30000, 20000, 10000]), 2)


def test_realign_shifted_row():
    # Křupky na břehu, Excel row 109
    recorded = {"start": 0.07, "run1": 4.98, "chg2": "vběhl", "run2": -0.1,
                "chg3": 5.13, "run3": "OK", "chg4": 5.36, "run4": None}
    cells, shifts, overflow = parse.realign_shifted_row(recorded)
    assert shifts == 1 and overflow is None
    assert cells == {"start": 0.07, "run1": 4.98, "chg2": None, "run2": "vběhl",
                     "chg3": -0.1, "run3": 5.13, "chg4": "OK", "run4": 5.36}


def test_realign_leaves_normal_rows_alone():
    row = {"start": 0.1, "run1": 4.0, "chg2": "ok", "run2": "mimo",
           "chg3": None, "run3": 4.2, "chg4": -0.05, "run4": 4.1}
    assert parse.realign_shifted_row(row) == (row, 0, None)


@pytest.mark.parametrize("breed, group", [
    ("Border Collie", "Border Collie"), ("border collie", "Border Collie"),
    ("BorderCollie", "Border Collie"), ("Border", "Border Collie"),
    ("Mix", "Mix"), ("Keverék", "Mix"), ("Whippet", "Other"),
])
def test_breed_group(breed, group):
    assert dogs.breed_group(breed) == group


@pytest.mark.parametrize("ulna, height", [
    (10.0, 15.0), (10.02, 17.5), (12.5, 20.0), (12.6, 22.5), (16.28, 30.0), (17.55, 32.5)])
def test_fci_jump_height(ulna, height):
    assert dogs.fci_jump_height(ulna) == height
