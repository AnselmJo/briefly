# Briefly (Daily Cast)

Persönliches tägliches Audio-Briefing: eine ~10-minütige Sprachfolge, die
automatisch aus News-Feeds, Wissens-Themen und einer lokalen Text-Inbox
kuratiert, per lokalem LLM zu einem Sprechtext-Skript geschrieben und per
lokalem TTS zu einer Audiodatei mit Kapitelmarken gerendert wird. Ausgeliefert
über einen simplen RSS-Feed im Heimnetz. MVP-Zielgruppe: der Nutzer selbst
plus ein paar Freunde/Familie, komplett lokal auf einem Mac M4, ohne
Cloud-Aufrufe außer den konfigurierten Quellen.

Vollständiges fachliches Briefing: @docs/concept/01-briefing-fuer-claude-fable.md
Branding/Design: @docs/concept/03-branding-design-konzept.md

## Tech-Stack

- Python 3.12+, `pydantic` für strukturierte Daten/Config-Validierung
- `ollama` (offizielles Python-Paket) für das lokale LLM
- lokales TTS-System (Wahl noch offen, siehe unten)
- `feedparser` für RSS, `httpx` für HTTP, `pyyaml` für Config
- `ffmpeg` (extern, per Subprocess) für Audio-Nachbearbeitung/Kapitelmarken
- `pytest` für Tests, `ruff` für Linting/Formatierung

## Befehle

Noch kein Code vorhanden (Phase 0 = nur Grundgerüst). Sobald implementiert:

```
pip install -e ".[dev]"
pytest
ruff check .
ruff format .
```

## Architekturregel: Provider-Abstraktion (nicht verhandelbar)

Der Pipeline-Kern (`src/briefly/pipeline.py`, `models.py`) darf **nie** einen
konkreten Dienst direkt ansprechen. Alle Zugriffe auf externe
Dienste/Systeme laufen über eines der vier Provider-Pakete, jeweils mit
`base.py` (Protocol) und einer lokalen MVP-Implementierung:

- `sources/` – `ContentSource` (Inbox, RSS; später Kalender/Events)
- `llm/` – `LanguageModelProvider` (MVP: Ollama)
- `tts/` – `SpeechSynthesisProvider` (MVP: lokales TTS)
- `delivery/` – `DeliveryTarget` (MVP: lokaler Ordner + RSS-XML)

Grund: das ist die Grundlage für spätere Cloud-Provider und Mehrnutzer-
Fähigkeit. Fehlt die Trennung, muss später alles neu geschrieben werden.

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
  Feeds, Sprache, Zeiten, Segment-Profil), lebt in `config/config.yaml`
  (siehe `config/config.example.yaml`), nie im Code.
- Fehlertoleranz: fällt eine Quelle aus, läuft die Pipeline trotzdem durch –
  nur ohne das betroffene Segment.
- Kein stiller Datenabfluss: alles lokal, keine Cloud-Aufrufe außer den
  explizit konfigurierten Quellen (RSS/APIs).
- Jede Pipeline-Stufe (Sammeln, Kuratieren, Skript, Audio, Ausliefern) muss
  einzeln aufrufbar/testbar sein.
- Einfachheit vor Cleverness: der Nutzer ist Data Analyst, kein
  Vollzeit-Entwickler – die verständlichere Variante gewinnt, sofern nicht
  grob ineffizient.

## Offene Entscheidungen (noch nicht getroffen, Phase 0 nimmt sie nicht vorweg)

- Wahl des lokalen TTS-Systems.
- Default-Ollama-Modell.
- Exaktes normalisiertes Item-Datenformat zwischen Pipeline-Stufen.
- Technik für Kapitelmarken (Marker-Tokens vs. getrennte TTS-Aufrufe je
  Segment).

Details und Begründungspflicht dazu: siehe Briefing §9.
