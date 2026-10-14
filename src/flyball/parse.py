"""Interpretation of raw sheet values: titles, competition days and time cells."""

import math
import re
from datetime import date

import pandas as pd

from flyball import config

# --- Titles -------------------------------------------------------------------

_TITLE_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<venue>[^)]+)\)\s*(?P<year>\d{4})\.\s*"
    r"(?P<month>[^\s\d]+)\s+(?P<d1>\d{1,2})(?:-(?P<d2>\d{1,2}))?\.?\s*$"
)
_RING_RE = re.compile(r"\s*(?:-\s*)?(?:(?P<a>\d)\.\s*ring|ring\s*(?P<b>\d))\s*$", re.IGNORECASE)


def parse_title(title: str) -> dict:
    """Split a B1 title into competition, ring, venue and the list of dates.

    >>> parse_title("Eager´s Cup 1. ring (Žamberk) 2023. május 6-7.")["ring"]
    1
    """
    m = _TITLE_RE.match(title.strip())
    if not m:
        raise ValueError(f"Unrecognised title: {title!r}")
    name, ring = m["name"].strip(), None
    r = _RING_RE.search(name)
    if r:
        ring = int(r["a"] or r["b"])
        name = name[: r.start()].strip()
    year, month = int(m["year"]), config.HUNGARIAN_MONTHS[m["month"].lower()]
    last_day = int(m["d2"] or m["d1"])
    dates = [date(year, month, d) for d in range(int(m["d1"]), last_day + 1)]
    return {"competition": name, "ring": ring, "venue": m["venue"].strip(), "dates": dates}


# --- Competition days ---------------------------------------------------------

def assign_day_index(seconds_of_day: pd.Series, n_days: int) -> pd.Series:
    """0-based competition day for each row, from drops in time of day.

    Rows are in running order, so each new day starts where the clock goes
    backwards (evening -> next morning). The number of drops must equal
    `n_days - 1`; anything else means the sheet isn't what we expect.
    """
    drops = seconds_of_day.diff() < 0
    if drops.sum() != n_days - 1:
        raise ValueError(f"Expected {n_days - 1} day break(s), found {drops.sum()}")
    return drops.cumsum().astype(int)


# --- Time cells -----------------------------------------------------------------

def classify_time(value, slot: str) -> tuple[float, str]:
    """Interpret one time cell as (seconds, code).

    `slot` is "start", "chg" (changeover) or "run". Codes:
      number        a normal time
      ok            "ok" pass, counted as 0.00 s
      false_start   negative start
      early_pass    negative changeover (quantified early pass)
      error         early pass detected but not quantified (chyba / error)
      outside       dog went outside / missed a hurdle (mimo / outside)
      run_in        dog ran in / behind the box (vběhl / run in)
      negative_run  negative number in a run cell (invalid)
      missing       empty cell
      unknown_text  any other text
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan, "missing"
    if isinstance(value, str):
        code = config.TEXT_CODES.get(value.strip().lower(), "unknown_text")
        return (0.0 if code == "ok" else math.nan), code
    seconds = round(float(value), config.ROUND_DP)
    if seconds < 0:
        return seconds, {"start": "false_start", "chg": "early_pass", "run": "negative_run"}[slot]
    return seconds, "number"


RUN_FAULT_CODES = {"outside", "run_in"}
PASS_FAULT_CODES = {"false_start", "early_pass", "error"}

# Slot sequence of one row, in recording order.
SLOT_SEQUENCE = ["start", "run1", "chg2", "run2", "chg3", "run3", "chg4", "run4"]


def realign_shifted_row(cells: dict) -> tuple[dict, int, object]:
    """Undo the one-cell shift that follows a run-in code in a changeover cell.

    When a dog ran in, some recorders typed the run-fault code into that
    dog's *changeover* cell and every following value one cell too early
    (see ANALYSIS_LOG Step 1.4). Signature: a run-fault text in a `chg` cell.
    Fix: the code moves to the run cell, the changeover becomes empty, and
    every later value moves one slot right. The value pushed off the end of
    the row is returned as `overflow`.

    Returns (realigned cells, number of shifts applied, last overflow value).
    """
    cells, shifts, overflow = dict(cells), 0, None
    while True:
        bad = next(
            (s for s in SLOT_SEQUENCE
             if s.startswith("chg") and isinstance(cells[s], str)
             and config.TEXT_CODES.get(cells[s].strip().lower()) in RUN_FAULT_CODES),
            None,
        )
        if bad is None:
            return cells, shifts, overflow
        i = SLOT_SEQUENCE.index(bad)
        tail = [cells[s] for s in SLOT_SEQUENCE[i:]]
        overflow = tail[-1]
        new_tail = [None] + tail[:-1]
        cells.update(zip(SLOT_SEQUENCE[i:], new_tail))
        shifts += 1
