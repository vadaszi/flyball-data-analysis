# WRFT 2023 – prezentáció és interaktív weboldal

Ez a mappa önálló: minden fájl benne van, amire a weboldalnak szüksége van, internetkapcsolat nélkül is működik.

| Fájl | Mi ez? |
|---|---|
| `index.html` | Az interaktív weboldal. Dupla kattintással megnyitható böngészőben. |
| `WRFT_2023_elemzes.pdf` | A prezentáció: a fő rész a 10–12 perces előadáshoz, utána a részletes függelék. |
| `WRFT_2023_eloadoi_jegyzet.pdf` | Előadói jegyzet diánként, időzítéssel. |
| `adatok/` | Letölthető táblák (CSV, Excelben megnyitható). |
| `assets/` | A weboldal stílusa, ábrái, betűtípusa és adatai – ne nevezd át. |

## Feltöltés

A teljes mappát kell feltölteni, a szerkezetét megtartva. Bármely statikus tárhely jó, például:

- **GitHub Pages:** a mappa tartalmát egy repository gyökerébe (vagy `docs/` mappájába) kell tenni, majd a Settings → Pages menüben bekapcsolni.
- **Netlify Drop** (app.netlify.com/drop): a mappát egyszerűen rá kell húzni az oldalra.
- Bármilyen webtárhely FTP-vel: a mappa tartalmát a webes gyökérkönyvtárba kell másolni.

A weboldal a PDF-et relatív hivatkozással éri el, ezért a PDF-nek az `index.html` mellett kell maradnia.

## Frissítés

A mappát a projektből a `uv run python scripts/run_phase6_presentation.py` parancs építi újra; kézzel ne szerkeszd.
