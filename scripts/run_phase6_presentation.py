"""Phase 6: the Hungarian presentation (PDF) and the interactive website, in one folder.

  charts        figures/phase6/*.svg                      (flyball.plots.deck)
  deck          prezentacio/WRFT_2023_elemzes.pdf          (flyball.report.deck; HTML in reports/phase6/)
  notes         prezentacio/WRFT_2023_eloadoi_jegyzet.pdf
  website       prezentacio/index.html + assets/ + adatok/ (flyball.report.site)

Every number on the slides and the site comes from reports/phase5/key_numbers.json or from the
report tables (flyball.report.numbers). Slide text: src/flyball/report/text_hu.toml.
Reads data/processed/ and reports/ (run the Phase 2-5 scripts first). Needs headless Chromium
(Playwright); see ANALYSIS_LOG 7.1 for the three local libraries it needs on this machine.

Usage:  ~/.local/bin/uv run python scripts/run_phase6_presentation.py [--screenshots DIR]
"""

import argparse
import time
from pathlib import Path

from flyball import config
from flyball.plots import deck as deck_plots
from flyball.report import deck, figdata, site

OUT = config.ROOT / "prezentacio"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screenshots", type=Path, help="also write one PNG per slide into this folder")
    args = ap.parse_args()
    t0 = time.time()

    charts = deck_plots.build_all(figdata.chart_inputs())
    print(f"Charts: {len(charts)} SVGs in {config.FIGURES / 'phase6'}")

    built = deck.build(OUT)
    print(f"Deck: {built['pdf'].relative_to(config.ROOT)} ({len(deck.load_text()['slide'])} slides), "
          f"notes: {built['notes_pdf'].relative_to(config.ROOT)}")
    if args.screenshots:
        shots = deck.screenshots(built["html"], args.screenshots)
        print(f"Screenshots: {len(shots)} PNGs in {args.screenshots}")

    web = site.build(OUT)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e6
    print(f"Website: {web['index'].relative_to(config.ROOT)} + assets/ + adatok/ ({len(web['csvs'])} CSVs)")
    print(f"Folder {OUT.relative_to(config.ROOT)}/: {size:.1f} MB, built in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
