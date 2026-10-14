"""Raw reader for the competition workbooks.

Reads cell values **and** the font colours that carry hidden information:
- the font colour of the team cell (column D) is the lane (red/blue);
- a red font on a time cell (columns J-T) marks a fault.

Values are returned as stored in Excel; interpretation happens in `parse.py`.
pandas.read_excel can't be used here because it drops cell styles.
"""

from datetime import datetime, time
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl.styles.colors import COLOR_INDEX

from flyball import config

MAX_BLANK_RUN = 20


def _palette(workbook) -> list[str]:
    """Indexed-colour palette of the workbook as 6-digit RGB hex strings.

    The EFC workbook defines its own palette in styles.xml, which openpyxl
    exposes as the (private) `_colors` attribute; otherwise use the default.
    """
    colours = workbook._colors or COLOR_INDEX
    return [c[-6:].upper() for c in colours]


def font_rgb(cell, palette: list[str]) -> str | None:
    """Font colour of a cell as a 6-digit RGB hex string, or None if themed/unset."""
    colour = cell.font.color if cell.font else None
    if colour is None:
        return None
    if colour.type == "rgb":
        return colour.rgb[-6:].upper()
    if colour.type == "indexed" and colour.indexed < len(palette):
        return palette[colour.indexed]
    return None  # theme colours: the normal black text


def time_of_day_seconds(value) -> float | None:
    """Seconds since midnight from the `kdy`/`when` cell.

    openpyxl returns a `time` for CZ cells (pure day fraction) and a
    `datetime` for EFC cells (stored as 1 + fraction); only the clock part
    is meaningful in both cases.
    """
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6
    if isinstance(value, (int, float)):
        return round((value % 1) * 86400, 3)
    return None


def read_sheet(worksheet, palette: list[str]) -> tuple[str, pd.DataFrame]:
    """Read one competition sheet: (title from B1, one row per data row).

    Columns B-T are read by position. Rows with an empty team cell (D) are
    skipped: Eager's Cup has one blank separator row at the day break.
    Reading stops after `MAX_BLANK_RUN` blank rows in a row, because the EFC
    sheets carry ~1000 formatted empty rows.
    """
    title = worksheet[config.TITLE_CELL].value
    n_cols = len(config.SHEET_COLUMNS)
    time_idx = [config.SHEET_COLUMNS.index(c) for c in config.TIME_COLUMNS]

    records, blank_run = [], 0
    for row in worksheet.iter_rows(min_row=config.FIRST_DATA_ROW, max_col=n_cols):
        team_cell = row[config.TEAM_COL - 1]
        if team_cell.value is None:
            blank_run += 1
            if blank_run >= MAX_BLANK_RUN:
                break
            continue
        blank_run = 0
        rec = {name: cell.value for name, cell in zip(config.SHEET_COLUMNS, row)}
        rec["excel_row"] = team_cell.row
        rec["lane_rgb"] = font_rgb(team_cell, palette)
        for i in time_idx:
            rec[f"red_{config.SHEET_COLUMNS[i]}"] = font_rgb(row[i], palette) == config.FAULT_FONT_RGB
        records.append(rec)

    df = pd.DataFrame.from_records(records)
    df["seconds_of_day"] = df["when"].map(time_of_day_seconds)
    df["lane"] = df["lane_rgb"].map(config.LANE_BY_RGB)
    return title, df


def read_workbook(source: str, path: Path) -> list[tuple[str, str, pd.DataFrame]]:
    """Read every sheet of a competition workbook as (sheet name, title, rows)."""
    workbook = openpyxl.load_workbook(path, data_only=True)
    palette = _palette(workbook)
    out = []
    for ws in workbook.worksheets:
        title, df = read_sheet(ws, palette)
        df.insert(0, "source", source)
        df.insert(1, "sheet", ws.title)
        out.append((ws.title, title, df))
    return out


def read_all() -> list[tuple[str, str, pd.DataFrame]]:
    """Read both competition workbooks (CZ first, then EFC), sheets in file order."""
    return [
        item
        for source, path in config.COMPETITION_XLSX.items()
        for item in read_workbook(source, path)
    ]
