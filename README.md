<h1 align="center">🎬 FurServer – Moderní domácí YouTube/Galerie server v Pythonu</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/flask-Modern%20Web%20UI-red?logo=flask">
  <img src="https://img.shields.io/badge/design-YouTube%20Dark%20Mode-black?logo=youtube">
</p>

---

## 🚀 Funkce

- **Nahrávání videí i fotek** přes moderní popup s náhledem a možností zadat vlastní název
- **Oddělené galerie** pro videa a fotky
- **Vyhledávání, řazení a filtrování** podle názvu, data, velikosti, délky sledování
- **Přejmenování a mazání** souborů přímo z webového rozhraní
- **Sledování pozice přehrávání videa** (pokračování tam, kde jste skončili)
- **Responzivní a nadčasový design** inspirovaný YouTube (tmavý režim, animace)
- **Plně v Pythonu (Flask)**, žádné Node.js nebo Next.js

---

## 🛠️ Instalace a spuštění

```bash
git clone https://github.com/hovnokleslo14/furserver.git
cd furserver
pip install flask
python app.py
```

- Otevřete v prohlížeči: [http://localhost:5000](http://localhost:5000)

---

## 📂 Struktura projektu

```
furserver/
│
├── app.py                # Hlavní Flask aplikace
├── videos/               # Složka s videi a metadata.json
├── photos/               # Složka s fotkami a metadata.json
├── static/
│   └── style.css         # Moderní YouTube-like styl
├── templates/
│   └── index.html        # Hlavní webové rozhraní
└── README.md             # Tato dokumentace
```

---

## ✨ Použití

- **Nahrání:** Klikněte na ikonu nahrávání vpravo nahoře, vyberte typ souboru (video/fotka), zadejte název (volitelné), nahrajte a potvrďte.
- **Vyhledávání:** Použijte vyhledávací pole pro videa nebo fotky.
- **Řazení:** Řaďte podle názvu, data, velikosti, délky sledování.
- **Mazání/Přejmenování:** Použijte tlačítka pod každým souborem.
- **Přehrávání:** Klikněte na náhled videa nebo fotky.

---

## 📝 Poznámky

- **Videa** jsou ukládána do složky `videos/`, **fotky** do `photos/`.
- **Metadata** (název, velikost, pozice přehrávání) jsou ukládána do `metadata.json` v příslušné složce.
- **Podporované formáty videí:** mp4, webm, ogg, mkv  
  **Podporované formáty fotek:** jpg, jpeg, png, gif, bmp, webp

---

## 💡 Tipy

- Pro nasazení na veřejný server doporučujeme nastavit `debug=False` a použít např. [gunicorn](https://gunicorn.org/) nebo [waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/).
- Pro větší knihovny doporučujeme použít SSD disk.

---

## 📜 Licence

GPL-3.0 license

---

<p align="center">
  <b>Vytvořil Furplex &nbsp;|&nbsp; 2025</b>
</p>
