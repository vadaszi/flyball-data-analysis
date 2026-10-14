# Flyball Elemzés Projekt

## Szituáció

Ebben a projektben egy kitalált, mégis igazán életszerű helyzetben tesztelheted adatelemzői képességeidet. A projektben egy fiktív Flyball csapat, a **Wild Runners Flyball Team (WRFT)** edzője kért segítséget a csapata 2023-as verseny eredményeinek feldolgozásában. 

A cél, hogy az elemzéseket felhasználva a jövőben még jobb teljesítményt nyújthasson a csapat.

> **Mi az a Flyball?**  
> A Flyball egy váltó csapatverseny kutyáknak, ahol a résztvevők akadályokat ugorva hoznak vissza egy labdát egy speciális dobozból.

---

## Feladat

A WRFT edzője először is szeretne egy általános képet kapni a csapatok és csapattagok elmúlt évi teljesítményéről (futási időkről, rajtolási időkről, váltási időkről, hibákról). Emellett az általános kép mellett vannak specifikus kérdései is.

### Specifikus kérdések:
1. Szignifikáns hatással van-e a kutyák futási teljesítményére az, hogy **melyik színű pályán** futnak?
2. Szignifikáns hatással van-e a kutyák futási teljesítményére az, hogy **ivaros/ivartalan kanra/szukára** vált rá a kutya?
3. Az összes eddigi elemzést (a korábbi alap elemzéseket) **versenyekhez (helyszínekhez és dátumokhoz) rendelve** szeretné látni, hogy az információk még beszédesebbek legyenek.

### Extra kérés (Időjárás hatásai):
Az edző szeretné **időjárási adatok függvényében** vizsgálni a teljesítményeket (kutyák és csapatok szintjén), mivel gyanítja, hogy a hőmérséklet, szélerősség, páratartalom és csapadékmennyiség befolyásolja a kutyák teljesítményét. Mivel erről nincsenek feljegyzései:
* Csatolj időjárási adatokat minden versenyadathoz!
* Támaszd alá vagy cáfold meg az edző időjárással kapcsolatos sejtését elemzésekkel!
* Szívesen fogadna javaslatokat a **legideálisabb csapatösszeállításra** is.

Az alkalmazott módszertan (bar chartok, korrelációs elemzés, ML modell) teljes mértékben rád van bízva.

### Értékeléshez szükséges leadandók:
* **Kód:** Az elemzéseket megfelelő formátumú fájlban/fájlokban készítsd el (`.sql`, `.ipynb`, `.py`, `.sh`).
* **Prezentáció:** Az üzleti találásokról készíts egy prezentációt `.pdf` formátumban. Javasolt egy 10-12 perces üzleti prezentáció összefoglalóját elkészíteni a megrendelő számára.

---

## Adat

A WRFT edzője 3 Excel táblát bocsátott rendelkezésre:

1. **Kutyák alapadatai** (1 Excel tábla, valós, maszkolt adatok):
   * *Letöltés:* `Wild_Runners_Flyball_Team_kutyak_alapadatai`
2. **2023-as versenyadatok** (2 Excel tábla, összesen 12+4 adatlappal, 11 verseny eredményeivel, maszkolt adatok):
   * *Letöltés:* `FLYBALLCZ_versenyadatok`
   * *Letöltés:* `EFC_versenyadatok`
3. **Dokumentáció** (részletes magyarázó fájl a datasethez):
   * *Letöltés:* `WRFT_dokumentacio`

---

## Domain Tudás

A flyball-lal kapcsolatos szakmai háttértudást az alábbi forrásokból érdemes elsajátítani:

* **YouTube:** [A 2023-as CRUFTS Flyball döntője](https://www.youtube.com/watch?v=FDUHV3LjISY)
* **Wikipédia:** [Flyball (angol nyelvű leírás)](https://en.wikipedia.org/wiki/Flyball)
* **Szabályzat 1:** [Magyar Flyball Versenyszabályzat](https://www.dogland.hu/images/pdf/szabalyzatok/flyball-szabalyzat.pdf) *(Megjegyzés: a kutyák méréséről és az ugróakadályok magasságáról szóló rész elavult)*
* **Szabályzat 2:** [UKFL Hungary 9. fejezet (Kutyák mérése és akadálymagasság)](https://www.ukflyball.org.uk/wp-content/uploads/2019/12/UKFL-Svab-Ford-1-o.pdf)

---

## Javasolt Elemzési Fázisok

1. **Feltáró adatelemzés** - domain kérdések megfogalmazása, összegyűjtése.
2. **Adattisztítás.**
3. **Alapelemzések** - rajtolási idők, futási idők, váltási idők, hibák.
4. **Összetettebb elemzések** - korrelációk, versenyekhez rendelés, időjárási adatok hozzákapcsolása és elemzése.
5. **Felismert összefüggések rendszerezése.**
6. **Adatvizualizáció.**

---

## Pontozási Szempontok

A projekt értékelése során az alábbi szempontok érvényesülnek (Összesen: 100 pont):

### 1. Üzleti Érték (50 pont)
* **Azonnal használható, üzleti eredményt generáló, adatokkal igazolt információ:** Olyan tudás, amivel a csapat jobb eredményeket érhet el. A "jó eredmény" definiálása az elemző feladata.
* **Data Science szakmai minőség:** Az állítások legyenek adatokkal, szakmailag elfogadható módon igazolva.
* **Részletesség:** Milyen mélyen tárja fel a problémákat az elemzés és a kutatás.

### 2. Kódolás (30 pont)
* **Adatos szakmai hibáktól mentes kód:** Statisztikai és adattisztítási hibák elkerülése.
* **Tiszta kód:** Olvasható, könnyen szerkeszthető és bővíthető kód (kommentek, struktúra, modularitás).
* **Kódminőség:** Tömör, elegáns, nem repetitív kód.

### 3. Vizualizáció (20 pont)
* **Érthetőség és dizájn:** Könnyen befogadható és lényegre törő prezentáció.
* **Kreativitás és innováció:** Az ismert vizualizációs technikák érdekes/új felhasználása. *(Bónusz pont adható új vagy kevésbé ismert technikák hatékony alkalmazásáért).*