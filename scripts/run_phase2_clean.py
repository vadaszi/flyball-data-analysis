"""Phase 2: rebuild all cleaned tables in data/processed/ from the raw Excel files.

Usage:  ~/.local/bin/uv run python scripts/run_phase2_clean.py
"""

from flyball import clean, config


def main() -> None:
    tables = clean.build_all()
    clean.write_outputs(tables)

    heats, runs = tables["heats"], tables["runs"]
    print(f"Wrote tables to {config.PROCESSED}")
    print(f"  competitions: {len(tables['competitions'])} sheet-days")
    print(f"  heats:        {len(heats)} team rows in {heats['heat_id'].nunique()} heats, "
          f"{heats['race_id'].nunique()} races")
    print(f"  runs:         {len(runs)} dog slots, {runs['valid_speed'].sum()} valid for speed")
    print(f"  WRFT:         {heats['is_wrft'].sum()} rows, "
          f"{runs.loc[runs['is_wrft_dog'], 'dog_key'].nunique()} dogs")
    print("\nData-quality checks:")
    print(tables["data_quality"].to_string(index=False))


if __name__ == "__main__":
    main()
