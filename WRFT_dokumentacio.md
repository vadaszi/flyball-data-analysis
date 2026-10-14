# WRFT Adatszótár és Adatstruktúra

Ez a dokumentum a Wild Runners Flyball Team (WRFT) 2023-as adatbázisainak részletes leírását tartalmazza. Az elemzéshez három fő Excel fájl áll rendelkezésre.

---

## 1. Wild_Runners_Flyball_Team_kutyak_alapadatai

A WRFT összes (51) kutyájának alapadatait tartalmazó táblázat, amelyet a csapat edzője folyamatosan frissít az új csapattagok érkezésekor.

### Oszlopok leírása:
* **felvezeto:** A kutya felvezetőjének azonosítója (Formátum: 2 betűből és 6 számjegyből álló kód).
* **nev:** A kutya neve.
* **fajta:** A kutya fajtája.
* **nem:** A kutya neme (Értékek: `kan`, `szuka`).
* **ivar:** Az ivar állapota (Értékek: `ivaros`, `ivartalan`).
* **szuletesi_datum:** A kutya születési dátuma (Formátum: `YYYY-MM-DD`).
* **chip_szam:** A kutya chipjének azonosítója (Formátum: 14 számjegyű szám).
* **ulna_hossz:** A kutya alkarcsontjának (ulnájának) hossza. Ez az adat az ugrási magasság meghatározásához szükséges.
* **ugrasi_magassag:** A kutya számára a versenyeken előírt ugrási magasság.

---

## 2. FLYBALLCZ_versenyadatok

Ez az Excel fájl 12 munkalapon (sheet) tartalmazza a WRFT összes 2023-as csehországi versenyének eredményeit. 

**Struktúra és metaadatok:**
* **Munkalapok (Sheet-ek) neve:** A verseny nevét viseli. Ha egy verseny több ringben zajlott, ahhoz több sheet is tartozhat.
* **Fejléc:** Minden munkalapon a legelső sorba beszúrtak egy extra sort, amely a verseny nevét, helyszínét és dátumát tartalmazza.

### Oszlopok leírása:
* **nevtelen:** A versenyen lefutott futamok sorszáma.
* **Divize:** A divízió sorszáma.
* **kdy:** A futam időpontja (Formátum: `HH:MM:SS`).
* **kdo:** A vizsgált csapat neve (amelynek az adatait az adott sor tartalmazza).
* **s kým:** Az ellenfél csapat neve.
* **celkem:** A csapat által futott összesített idő.
* **V/P/R:** A futam kimenetele. Értékek: `V` = győzelem (Vítězství), `P` = vereség (Prohra), `R` = döntetlen (Remíza).
* **překážky:** Az akadályok magassága.
* **jméno (oszlopok):** Az adott pozícióban (1-4.) futó kutya neve.
* **1.pes, 2.pes, 3.pes, 4.pes:** Az adott pozícióban futó kutyák futási ideje.
    * *Speciális értékek (hibák):* Tartalmazhat `vbehl` (befutott a gép mögé) és `mimo` (kívül, akadályt került) szöveges értékeket is.
* **start:** Az 1. pozícióban futó kutya rajtolási ideje. 
    * *Speciális érték:* Tartalmazhat negatív időket is, amelyek a korai, hibás indításokat jelzik.
* **stříd. (oszlopok):** Az adott pozícióban futó kutyához tartozó váltási idők.
    * *Speciális érték (hiba):* Negatív idő, vagy `chyba` (olyan korai, hibás váltás, amit a gép érzékelt, de nem tudott számszerűsíteni).
    * *Speciális érték (tökéletes):* `ok` és `OK` értékek, amelyek a közel tökéletes (0,00 másodperces) váltásokat jelölik.

---

## 3. EFC_versenyadatok

Ez a fájl 4 munkalapon tartalmazza az European Flyball Championships 2023 verseny eredményeit.

**Struktúra és metaadatok:**
* **Munkalapok (Sheet-ek) neve:** A ring számát és a versenynap számát jelöli.
* **Fejléc:** Minden munkalap első sora tartalmazza a ring számát, a verseny helyszínét és a dátumot.

### Oszlopok leírása:
* **nevtelen:** A versenyen lefutott futamok sorszáma.
* **Division:** A divízió sorszáma.
* **when:** A futam időpontja (Formátum: `HH:MM:SS`).
* **who:** A vizsgált csapat neve.
* **with who:** Az ellenfél csapat neve.
* **total time:** A csapat által futott összesített idő.
* **W/L/T:** A futam kimenetele. Értékek: `W` = győzelem (Win), `L` = vereség (Loss), `T` = döntetlen (Tie).
* **Hurdles:** Az akadályok magassága.
* **name (oszlopok):** Az adott pozícióban (1-4.) futó kutya neve.
* **1.dog, 2.dog, 3.dog, 4.dog:** Az adott pozícióban futó kutyák futási ideje.
    * *Speciális értékek (hibák):* Tartalmazhat `ran in` (befutott a gép mögé) és `outside` (kívül, akadályt került) szöveges értékeket is.
    * *Figyelem:* A második munkalapon (sheet-en) ezek a hibákhoz tartozó szöveges adatok valamiért **cseh nyelven** jelennek meg az angol helyett!
* **start:** Az 1. pozícióban futó kutya rajtolási ideje. 
    * *Speciális érték:* Negatív idők (korai, hibás indítás).
* **chng (oszlopok):** Az adott pozícióban futó kutyához tartozó váltási idők.
    * *Speciális érték (hiba):* Negatív idő, vagy `error` (olyan korai, hibás váltás, amit a gép érzékelt, de nem tudott számszerűsíteni).
    * *Speciális érték (tökéletes):* `ok` és `OK` értékek (0,00 másodperces váltások).