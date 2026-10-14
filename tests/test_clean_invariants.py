"""Invariants of the cleaned tables, checked against facts established in
Step 0 (data_structure.md) and Step 1 (ANALYSIS_LOG.md)."""

import pytest

from flyball import clean

# sheet -> (data rows, WRFT rows, day-2 start index), from data_structure.md §3
SHEET_FACTS = {
    "Hanácké škvarek": (235, 161, 109),
    "Eager´s Cup 1": (641, 120, 312),
    "Eager´s Cup 2": (705, 21, 329),
    "Flyvaryors turnaj": (740, 81, 354),
    "MED's Trophy": (579, 0, 284),
    "BCCCZ mistrovství": (389, 184, 184),
    "Crazy Cup": (824, 149, 386),
    "Máchale, spadlo ti to!": (668, 75, 314),
    "Mistrovství České republiky": (521, 113, 241),
    "Křupky na břehu": (607, 93, 290),
    "Budějckej xtreme 1": (728, 0, 338),
    "Budějckej xtreme 2": (758, 72, 356),
    "EFC_1 ring_1": (268, 15, None),
    "EFC_1 ring_2": (197, 23, None),
    "EFC_2 ring_1": (370, 14, None),
    "EFC_2 ring_2": (341, 7, None),
}


@pytest.fixture(scope="session")
def tables():
    return clean.build_all()


def test_row_counts(tables):
    heats = tables["heats"]
    assert len(heats) == 8571
    assert heats["is_wrft"].sum() == 1128
    assert heats["row_id"].is_unique


@pytest.mark.parametrize("sheet", SHEET_FACTS)
def test_per_sheet_facts(tables, sheet):
    n_rows, n_wrft, day2_at = SHEET_FACTS[sheet]
    rows = tables["heats"].query("sheet == @sheet").sort_values("row_id")
    assert len(rows) == n_rows
    assert rows["is_wrft"].sum() == n_wrft
    if day2_at is not None:
        assert (rows["day_index"].to_numpy() == 1).argmax() == day2_at


def test_lanes(tables):
    heats = tables["heats"]
    assert heats["lane"].isin(["red", "blue"]).all()
    for _, sheet in heats.groupby("sheet"):
        assert 0.45 <= sheet["lane"].eq("red").mean() <= 0.55
    paired = heats[heats["paired"]]
    assert paired.groupby("heat_id")["lane"].nunique().eq(2).all()


def test_no_heat_has_two_winners(tables):
    paired = tables["heats"].query("paired")
    assert not paired.groupby("heat_id")["outcome"].apply(lambda s: s.eq("win").all()).any()


def test_total_time_identity(tables):
    heats = tables["heats"]
    numeric = heats["identity_holds"].notna()
    assert numeric.sum() == 6286
    assert heats.loc[numeric, "identity_holds"].mean() == pytest.approx(0.889, abs=0.005)


def test_codes_in_the_right_cells(tables):
    heats = tables["heats"]
    for slot in clean.RUN_SLOTS:
        assert heats[f"{slot}_code"].isin(["number", "outside", "run_in", "missing"]).all()
    for slot in ["chg2", "chg3", "chg4"]:
        assert heats[f"{slot}_code"].isin(["number", "ok", "early_pass", "error", "missing"]).all()
    assert heats["start_code"].isin(["number", "false_start"]).all()
    assert heats["row_realigned"].sum() == 19


def test_red_font_marks_faults(tables):
    assert tables["heats"]["red_font_mismatch"].sum() <= 1     # one red "ok", Step 1.7


def test_wrft_dogs(tables):
    runs, dogs = tables["runs"], tables["dogs"]
    wrft = runs[runs["is_wrft_dog"]]
    assert wrft["dog_key"].nunique() == 50
    assert not wrft["wrft_name_unknown"].any()
    assert set(dogs["dog"]) - set(wrft["dog_key"]) == {"Fibo"}
    assert wrft["category"].notna().all()


def test_dog_master(tables):
    dogs = tables["dogs"]
    assert len(dogs) == 51
    assert dogs["ulna_corrected"].sum() == 4
    assert dogs["ulna_cm"].between(9, 19).all()
    assert dogs["category"].value_counts().to_dict() == {
        "neutered male": 22, "neutered female": 19, "intact male": 8, "intact female": 2}


def test_valid_speed_bounds(tables):
    valid = tables["runs"].query("valid_speed")["run_time"]
    assert valid.between(3.3, 10.0).all()


def test_flags_never_drop_rows(tables):
    runs, heats = tables["runs"], tables["heats"]
    assert set(runs["row_id"]) <= set(heats["row_id"])
    assert runs.groupby("row_id")["position"].apply(lambda s: s.is_unique).all()


def test_competitions(tables):
    comps = tables["competitions"]
    assert len(comps) == 28
    assert comps["n_rows"].sum() == 8571
    assert comps["competition"].nunique() == 11
    assert set(comps["weekday"]) == {"Saturday", "Sunday"}
