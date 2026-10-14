# WRFT Flyball 2023 analysis

Analysis of the Wild Runners Flyball Team's 2023 season. See `CLAUDE.md` and `plan.md`.

```bash
~/.local/bin/uv sync                                   # create the environment
~/.local/bin/uv run python scripts/run_phase2_clean.py # rebuild data/processed/
~/.local/bin/uv run pytest                             # tests
```
