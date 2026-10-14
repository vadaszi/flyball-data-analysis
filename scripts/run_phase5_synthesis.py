"""Phase 5: synthesis. Ranks every lever by extra heats won and collects the key numbers.

  impact ledger      reports/phase5/impact_ledger.csv (+ impact_day2_faults.csv, impact_meta.csv)
  key numbers        reports/phase5/key_numbers.json: every number findings.md and the deck quote,
                     with unit, CI, source table and log step

Reads data/processed/ and the Phase 3-4 tables in reports/ (run the earlier phase scripts first).
The prose deliverables, reports/findings.md and reports/storyline.md, are written from these outputs.

Usage:  ~/.local/bin/uv run python scripts/run_phase5_synthesis.py
"""

import json
import warnings

import pandas as pd

from flyball import config, metrics, synthesis

OUT = config.REPORTS / "phase5"


def main() -> None:
    t = metrics.load_processed()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # MixedLM boundary/convergence chatter (line-up profiles)
        out = synthesis.impact_ledger(t)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.round({c: 4 for c in df.select_dtypes("number").columns}).to_csv(OUT / f"{name}.csv", index=False)
    keys = synthesis.key_numbers()
    (OUT / "key_numbers.json").write_text(json.dumps(keys, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 80)
    m = out["impact_meta"].iloc[0]
    print(f"Wrote {OUT}: {len(out['impact_ledger'])} levers, {len(keys)} key numbers")
    print(f"\nImpact ledger: extra heats won per season ({int(m['external_decided_heats'])} decided heats "
          f"against other clubs; win rate now {m['win_rate']:.1%}):")
    cols = ["rank", "lever", "extra_wins", "ci_low", "ci_high", "club_win_rate_pp"]
    print(out["impact_ledger"][cols].round(2).to_string(index=False))
    print("\nSecond day vs first, WRFT heats (share of heats with each fault):")
    print(out["impact_day2_faults"].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
