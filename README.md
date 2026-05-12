# 🩸 GOON ETERNAL

> *A gothic raycaster shooter — survive 10 levels and defeat DRACULA.*

---

## 👥 Ihmiset projektin takana

| Nimi |
|------|
| Aleks |
| Veeti |
| Jasu |
| Aleksi |

---

## ⚙️ Vaatimukset

### Python
- **Python 3.10 – 3.13.x** (ei uudempaa kuin 3.13.x)

### Riippuvuudet

Asenna tarvittavat kirjastot komennolla:

```bash
pip install pygame pypresence
```

| Kirjasto | Käyttötarkoitus |
|----------|----------------|
| `pygame` | Peli-ikkuna, grafiikka, äänet, syötteet |
| `pypresence` | Discord Rich Presence -tuki |

### Standardikirjastot (ei asenneta erikseen)
Peli käyttää myös seuraavia Pythonin mukana tulevia kirjastoja:
`math`, `sys`, `random`, `time`, `os`, `heapq`, `json`

---

## 📁 Tiedostorakenne

```
GOON_ETERNAL/
├── GOON_ETERNAL.py
├── savegame.json          ← Luodaan automaattisesti tallennettaessa
└── media/
    ├── load.png           ← Latausruudun kuva / Discord RPC -kuva
    ├── (muut kuvatiedostot)
    └── (äänipätkät: death1-5.wav, 2-death.wav, 2-death2.wav, jne.)
```

> **Huom:** `media/`-kansio tulee olla samassa hakemistossa kuin `GOON_ETERNAL.py`.

---

## 🚀 Käynnistys

```bash
python GOON_ETERNAL.py
```

---

## 🎮 Ohjaimet

| Näppäin / Toiminto | Kuvaus |
|--------------------|--------|
| `W / A / S / D` | Liiku / straffe |
| `Hiiri` | Käännä katsetta |
| `Vasen hiirinappi` tai `SPACE` | Ammu |
| `E` | Avaa ovi |
| `SHIFT` | Sprinttaa |
| `ESC` | Pauseta / valikko |

---

## 🩸 LORE

GOON ETERNAL: VIIMEINEN EDGEYS

VUOSI 2026: Maailma ei päättynyt ydinsotaan, vaan Suureen Goonaukseen. Muinainen Dracula on kaapannut maailman naisväestön mielen "Morsiusverkkoon" – digitaaliseen goon-luolaan, jossa kukaan ei ole oma itsensä. Miehet on poistettu palvelimelta, ja maailma on vajonnut transsinomaiseen hiljaisuuteen.

THE VAULT: Kymmenen kerrosta puhdasta betonia ja kärsimystä. Se on Draculan päämaja, jossa hän hallitsee teknomagiasta käsin. Bunkkerin käytävät ovat täynnä tyhjiä katseita ja "moggaavia" vartijoita, jotka odottavat vain yhtä virhettä.

PERTTI: Viimeinen vapaa mies. Pertti ei ole mikään valittu sankari, hän on vain liian itsepäinen antautuakseen Draculan aivopesulle. Hän on bunkkerin ainoa häiriötekijä, The Last Gooner, joka ei suostu häviämään.

PELIMEKANIIKAT: Yksi työkalu, kymmenen kerrosta: Pertillä ei ole sorkkarautoja tai hienoja vempaimia. Hänellä on vain vanha, ruosteinen pumppuhaulikko. Ammuksia on säälittävän vähän, joten jokainen laukaus on tehtävä laskelmoidusti. Kun piippu laulaa, koko kerros herää.

The Grind: Raivaa tiesi alas asuinkerroksista, ohi hämärtyneiden kasvihuoneiden ja läpi öljyisten konehuoneiden. Jokainen kerros on askel lähemmäs Draculaa.

Final Boss: Alimmalla tasolla odottaa itse Dracula. Hän yrittää murtaa Pertin mielen teknologisella loitsullaan, mutta Pertti vastaa siihen lyijyllä.

TAVOITE: Laskeudu pohjalle, vältä joutumasta osaksi Draculan ikuista transsia ja paina liipaisinta.
---

## 💾 Tallennus

Peli tallentaa edistymisen automaattisesti tiedostoon `savegame.json`, joka luodaan pelin kansioon.

---

## 🎵 Discord Rich Presence

Jos Discord on käynnissä, peli näyttää automaattisesti mitä kenttää pelaat. Jos Discordia ei löydy, peli käynnistyy normaalisti ilman virhettä.
