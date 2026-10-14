"""WRFT dog master data: load, correct and enrich."""

import pandas as pd

from flyball import config

# Hungarian master-data columns -> English names used everywhere else.
COLUMN_NAMES = {
    "felvezeto": "handler_id",
    "nev": "dog",
    "fajta": "breed_raw",
    "nem": "sex_hu",
    "ivar": "neuter_hu",
    "szuletesi_datum": "birth_date",
    "chip_szam": "chip",
    "ulna_hossz": "ulna_cm_raw",
    "ugrasi_magassag": "jump_height_cm",
}


def breed_group(breed: str) -> str:
    """Border Collie / Mix / Other, tolerant of the sheet's spelling variants."""
    key = breed.strip().lower().replace(" ", "")
    if key.startswith("border"):
        return "Border Collie"
    if key in {"mix", "keverék"}:
        return "Mix"
    return "Other"


def fci_jump_height(ulna_cm: float) -> float:
    """Jump height from the FCI ulna table (a value on a limit gets the lower height)."""
    return next(height for limit, height in config.FCI_ULNA_TABLE if ulna_cm <= limit)


def load_dogs() -> pd.DataFrame:
    """Cleaned master data, one row per dog.

    pandas converts the date-formatted serial numbers itself (origin 1899-12-30).
    The four known ulna entry errors are corrected; the recorded jump height
    stays authoritative, and `jump_height_fci` is kept only as a check.
    """
    df = (
        pd.read_excel(config.DOGS_XLSX, dtype={"chip_szam": str})
        .dropna(how="all")
        .rename(columns=COLUMN_NAMES)
    )
    df["sex"] = df["sex_hu"].map({"kan": "male", "szuka": "female"})
    df["neutered"] = df["neuter_hu"].eq("ivartalan")
    df["category"] = (
        df["neutered"].map({True: "neutered", False: "intact"}) + " " + df["sex"]
    )
    df["breed_group"] = df["breed_raw"].map(breed_group)

    df["ulna_cm"] = df["dog"].map(config.ULNA_CORRECTIONS).fillna(df["ulna_cm_raw"])
    df["ulna_corrected"] = df["ulna_cm"].ne(df["ulna_cm_raw"])
    df["jump_height_fci"] = df["ulna_cm"].map(fci_jump_height)
    return df.drop(columns=["sex_hu", "neuter_hu"]).reset_index(drop=True)


def age_months(birth: pd.Series, on: pd.Series) -> pd.Series:
    """Age in (fractional) months, using the mean Gregorian month length."""
    return (pd.to_datetime(on) - pd.to_datetime(birth)).dt.days / 30.436875
