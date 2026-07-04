# Briefly (Daily Cast)

Persönliches tägliches Audio-Briefing: eine ~10-minütige Sprachfolge, die
automatisch aus News-Feeds, Wissens-Themen und einer lokalen Text-Inbox
kuratiert, per lokalem LLM zu einem Sprechtext-Skript geschrieben und per
lokalem TTS zu einer Audiodatei mit Kapitelmarken gerendert wird. Ausgeliefert
über einen RSS-Feed im Heim-WLAN, abonnierbar aus jeder Podcast-App (bevorzugt
AntennaPod auf Android). Eingaben/Einstellungen erfolgen über eine
responsive Web-Oberfläche, im Heim-WLAN von macOS/iOS/Windows/Android per
Browser erreichbar. Die Pipeline selbst läuft ausschließlich lokal auf einem
Mac (Apple Silicon), ohne Cloud-Aufrufe außer den konfigurierten Quellen.

Vollständiges fachliches Briefing: @docs/concept/01-briefing-fuer-claude-fable.md
Branding/Design: @docs/concept/03-branding-design-konzept.md

## Tech-Stack

- Python 3.12+, `pydantic` für strukturierte Daten/Config-Validierung
- `ollama` (offizielles Python-Paket) für das lokale LLM, Default-Modell `qwen3:8b`
- `piper-tts` für lokales TTS (Stimmen: `de_DE-thorsten-medium`, `en_US-lessac-medium`)
- `feedparser`/`httpx` für RSS, `feedgen` für die Feed-Erzeugung, `pyyaml` für Config
- `ffmpeg` (extern, per Subprocess) für Audio-Concat/Kapitelmarken
- `fastapi` + `uvicorn` + `jinja2` für die Web-Oberfläche
- `pytest` für Tests, `ruff` für Linting/Formatierung

## Befehle

```
pip install -e ".[dev]"
briefly run                 # komplette Pipeline (siehe cli.py für Einzelstufen)
uvicorn briefly.web.app:app --host 0.0.0.0 --port 8787   # Web-Oberfläche
pytest
ruff check .
ruff format .
```

## Architekturregel: Provider-Abstraktion (nicht verhandelbar)

Der Pipeline-Kern (`src/briefly/pipeline.py`, `models.py`) darf **nie** einen
konkreten Dienst direkt ansprechen. Alle Zugriffe auf externe
Dienste/Systeme laufen über eines der vier Provider-Pakete, jeweils mit
`base.py` (Protocol) und einer lokalen Implementierung:

- `sources/` – `ContentSource` (Inbox, RSS; später Kalender/Events)
- `llm/` – `LanguageModelProvider` (Ollama)
- `tts/` – `SpeechSynthesisProvider` (Piper)
- `delivery/` – `DeliveryTarget` (lokaler Ordner + RSS-XML via `feedgen`)

Grund: das ist die Grundlage für spätere Cloud-Provider und Mehrnutzer-
Fähigkeit. Fehlt die Trennung, muss später alles neu geschrieben werden.
Die Web-Oberfläche (`src/briefly/web/`) ist bewusst **kein** Teil dieser
Abstraktion – sie ist reine Ein-/Ausgabe (Config lesen/schreiben, Pipeline
anstoßen, Dateien ausliefern) und ruft nie direkt einen Provider auf.

## Code-Stil

- Deutsche Kommentare (stichpunktartig, nur wo sie echten Kontext liefern –
  keine Trivialkommentare), englische Bezeichner.
- Type Hints überall; `pydantic` (oder Dataclasses, wo `pydantic`
  überdimensioniert wäre) für strukturierte Daten.
- `pathlib` statt String-Pfadverkettung.
- Logging statt `print`, außer für lokale CLI-Ausgabe während der Entwicklung.
- Lieber mehrere kleine, klar benannte Funktionen als eine große. Keine
  Blockkommentare, keine überflüssige Verschachtelung.

## Nicht-funktionale Leitplanken

- Konfiguration statt Hardcoding: alles, was der Nutzer anpasst (Themen,
  Feeds, Sprache, Zeiten, Segment-Profil), lebt in `config.yaml`
  (siehe `config/config.example.yaml`) und ist über die Web-Oberfläche
  editierbar – nie im Code.
- Fehlertoleranz: fällt eine Quelle aus, läuft die Pipeline trotzdem durch –
  nur ohne das betroffene Segment.
- Kein stiller Datenabfluss: alles lokal, keine Cloud-Aufrufe außer den
  explizit konfigurierten Quellen (RSS/APIs). Web-Oberfläche und Feed sind
  nur im Heim-WLAN erreichbar, kein Tunnel/VPN, keine Authentifizierung nötig.
- Jede Pipeline-Stufe (Sammeln, Kuratieren, Skript, Audio, Ausliefern) muss
  einzeln aufrufbar/testbar sein (siehe `briefly.cli`-Subcommands).
- Einfachheit vor Cleverness: der Nutzer ist Data Analyst, kein
  Vollzeit-Entwickler – die verständlichere Variante gewinnt, sofern nicht
  grob ineffizient. Die Web-Oberfläche ist bewusst serverseitiges
  Jinja2-Rendering ohne Node/Build-Schritt, kein SPA-Framework.
- Wiedergabe erfolgt über bestehende Podcast-Apps (AntennaPod auf Android
  empfohlen) statt einer Eigenentwicklung – keine native App im Scope.

## Getroffene Entscheidungen (Briefing §9, mit Begründung)

- TTS: `piper-tts` (Open Home Foundation, aktiv gepflegt, native
  macOS-ARM64-Wheels, DE+EN-Stimmen).
- Ollama-Modell: `qwen3:8b` Default, `qwen3:14b` optional bei mehr RAM.
- Kapitelmarken: ffmpeg-Metadaten-Datei (`;FFMETADATA1`) beim finalen Mux zu
  `.m4b`, zusätzlich `chapters.json` (Podcasting 2.0) pro Episode.
- Item-Format: siehe `src/briefly/models.py` (`Item`, `ScriptSegment`,
  `EpisodeScript`, `ChapterMark`, `EpisodeManifest`).
- Testing: `pytest`, Provider werden in Pipeline-Tests über die
  `Protocol`-Schnittstellen gefaked (kein echter Ollama/Piper-Aufruf in der
  Standard-Testsuite nötig).
