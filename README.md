# GOON ETERNAL

> *A gothic raycaster shooter -- survive 10 levels and defeat DRACULA.*

---

## Ihmiset projektin takana

| Nimi |
|------|
| Aleks |
| Veeti |
| Jasu |
| Aleksi |

---

## Vaatimukset

### Python
- **Python 3.10 - 3.13.x** (ei uudempaa kuin 3.13.x)

### Riippuvuudet

Asenna tarvittavat kirjastot alla olevalla komennolla.

> **Huom Python-versiosta:** Jos sinulla on useita Python-versioita asennettuna, kayta versiota vastaavaa pip-komentoa. Esimerkiksi Python 3.11:lla `pip3.11 install pygame pypresence`, Python 3.12:lla `pip3.12 install pygame pypresence`. Windowsilla kokeile ensin `py -3.11 -m pip install pygame pypresence`.

```bash
pip install pygame pypresence
```

Jos `pip` ei toimi, kokeile:

```bash
python -m pip install pygame pypresence
```

| Kirjasto | Versio | Kayttotarkoitus |
|----------|--------|----------------|
| `pygame` | >= 2.5 | Peli-ikkuna, grafiikka, aanet, syotteet |
| `pypresence` | >= 4.3 | Discord Rich Presence -tuki |

### Standardikirjastot (ei asenneta erikseen)
`math`, `sys`, `random`, `time`, `os`, `heapq`, `json`

---

## Tiedostorakenne

```
GOON_ETERNAL/
+-- GOON_ETERNAL.py
+-- savegame.json          <- Luodaan automaattisesti tallennettaessa
+-- settings.json          <- Luodaan automaattisesti asetuksia muuttaessa
+-- highscores.json        <- Luodaan automaattisesti pelin jalkeen
+-- media/
    +-- load.png           <- Latausruudun kuva / Discord RPC -kuva
    +-- pistol.png         <- Pistooliase
    +-- shotgun.png        <- Haulikkokase
    +-- smg.png            <- Konepistooli
    +-- (muut kuvatiedostot)
    +-- (aanipatkAt: death1-5.wav, 2-death.wav, shot.wav, jne.)
```

> **Huom:** `media/`-kansio tulee olla samassa hakemistossa kuin `GOON_ETERNAL.py`.

---

## Kaynnistys

```bash
python GOON_ETERNAL.py
```

---

## Ohjaimet

### Liikkuminen

| Nappain | Kuvaus |
|---------|--------|
| `W` / `S` | Liiku eteen / taakse |
| `A` / `D` | Straffe vasemmalle / oikealle |
| `Hiiri` | Kaanna katsetta |
| `Vasen / Oikea nuolinappain` | Kaanna katsetta (vaihtoehto hiirelle) |
| `SHIFT` | Sprinttaa (kuluttaa kestavyytta) |

### Taistelu

| Nappain | Kuvaus |
|---------|--------|
| `Vasen hiirinappi` tai `SPACE` | Ammu |
| `1` | Vaihda aseeksi Pistooli (128 luotia, 2 dmg/laukaus) |
| `2` | Vaihda aseeksi Haulikko (64 patruunaa, 3 dmg/laukaus) |
| `3` | Vaihda aseeksi Konepistooli / SMG (256 luotia, 1 dmg/laukaus) |
| `Hiiren rulla` | Selaa aseita |

### Maailma ja valikot

| Nappain | Kuvaus |
|---------|--------|
| `E` | Avaa ovi / kayta parannusasemaa |
| `ESC` | Pauseta / avaa valikko |
| `R` | Aloita alusta (kuoleman jalkeen) |
| `L` | Nayta / piilota FPS-laskuri |
| `TAB` | Vaihda tulostaulun jarjestys (voittoruudussa) |

### Ammukset

Jokainen ase kayttaa omaa ammustyyppian. Ammolaatikot antavat kaikille aseille ammuksia samanaikaisesti:

| Ase | Ammustyyppi | Maksimi | Laatikosta |
|-----|-------------|---------|------------|
| Pistooli | Pistoolin patruunat | 128 | +8 |
| Haulikko | Haulikon patruunat | 64 | +4 |
| SMG | SMG-patruunat | 256 | +16 |

> Ammo-kapasiteettia voi kasvattaa **Max Ammo +12%** -parannuksella (kasvattaa kaikkia).

---

## Parannusasemat

Tasoilla 3, 6 ja 9 loytyyassa parannusasema. Lahesty sita ja paina `E`.
Parannuksia ostetaan **tokeneilla**, joita loytyy kentista.

| Parannus | Vaikutus |
|----------|----------|
| Damage x2 per tier | Tuplaa kaikkien aseiden perusvahingon |
| Fire Rate | Nopeuttaa laukausvahteja |
| Max Health | +5 maksimielama per taso |
| Max Stamina | +20 kestAvyys per taso |
| Stamina Recovery | Nopeampi kestAvyyden palautuminen |
| Max Ammo +12% | Kasvattaa kaikkien aseiden maksimimaaraa 12% |
| Armor | -5% saatu vahinko per taso |
| Ricochet | Luoti voi kimmahtaa seuraavaan viholliseen |
| Lifesteal | Mahdollisuus parantua tappojen yhteydessa |

Parannusten hinta nousee tason mukaan: tasot 1-2 maksavat 1 tokenin, tasot 3-4 maksavat 2 ja taso 5 maksaa 3 tokenia.

---

## Pisteiden kertoja

Tappaminen nopeasti perakkaain kasvattaa pistekertojaa:

| Tappomaara | Viesti | Kerroin |
|-----------|--------|---------|
| 3+ | TRIPLE KILL! | x2 |
| 5+ | KILLING SPREE! | x3 |
| 8+ | RAMPAGE! | x4 |
| 12+ | GODLIKE! | x5 |

Kerroin nollautuu jos 3 sekuntia kuluu ilman tappoa. Aktiivinen kerroin nakyyy HUD:ssa ajastimella.

---

## LORE

**GOON ETERNAL: VIIMEINEN EDGEYS**

VUOSI 2026: Maailma ei paattynyt ydinsotaan, vaan Suureen Goonaukseen. Muinainen Dracula on kaapannut maailman naisvaeston mielen "Morsiusverkkoon" -- digitaaliseen goon-luolaan, jossa kukaan ei ole oma itsensa. Miehet on poistettu palvelimelta, ja maailma on vajonnut transsinomaiseen hiljaisuuteen.

**THE VAULT:** Kymmenen kerrosta puhdasta betonia ja karsimysta. Se on Draculan paamaja, jossa han hallitsee teknomagiasta kasin. Bunkkerin kayravat ovat taynnA tyhjiA katseita ja "moggaavia" vartijoita, jotka odottavat vain yhta virhettA.

**PERTTI:** Viimeinen vapaa mies. Pertti ei ole mikaan valittu sankari, han on vain liian itsepAinen antautuakseen Draculan aivopesulle. Han on bunkkerin ainoa hairiotekija, The Last Gooner, joka ei suostu hAviAmAan.

**TAVOITE:** Laskeudu pohjalle, valta joutumasta osaksi Draculan ikuista transsia ja paina liipaisinta.

---

## Tallennus

Peli tallentaa edistymisen automaattisesti tiedostoon `savegame.json`. Asetukset tallennetaan `settings.json`-tiedostoon ja tulostaulukko `highscores.json`-tiedostoon -- kaikki luodaan automaattisesti pelin kansioon.

---

## Tulostaulukko

Pelin voittamisen jalkeen nakyy tulostaulukko, joka tallentaa **10 parasta suoritusta** seka pisteiden etta ajan mukaan. Naita voi selata `TAB`-nappaimella tai klikkaamalla valilehtiA voittoruudussa.

---

## Discord Rich Presence

Jos Discord on kaynnissa, peli nayttaa automaattisesti mita kenttaa pelaat. Jos Discordia ei loydy, peli kaynnistyy normaalisti ilman virhetta.
