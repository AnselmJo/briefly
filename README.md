# Briefly

Persönliches tägliches Audio-Briefing ("Daily Cast"): eine automatisch
generierte, ~10-minütige Sprachfolge aus News, Wissens-Themen und eigenen
Inbox-Einträgen (Notizen, Buchzusammenfassungen, Links), ausgeliefert als
abonnierbarer RSS-Feed. Läuft komplett lokal auf einem Mac (Apple Silicon).

> „Briefly – deine Themen, kurz und persönlich gesprochen, jeden Morgen."

Eingaben/Einstellungen erfolgen über eine Web-Oberfläche, die im Heim-WLAN
von macOS, iOS, Windows und Android aus per Browser erreichbar ist. Die
Wiedergabe (bevorzugt Android) erfolgt über eine bestehende Podcast-App wie
[AntennaPod](https://antennapod.org/) – Briefly liefert nur den RSS-Feed und
die Audiodateien mit Kapitelmarken, keine eigene App.

## Voraussetzungen

- macOS auf Apple Silicon, Python 3.12+
- [Ollama](https://ollama.com) installiert, Modell gezogen: `ollama pull qwen3:8b`
- `ffmpeg` installiert (z.B. `brew install ffmpeg`)
- Piper-Stimmen heruntergeladen (siehe unten)

## Installation

Repo klonen
Python installieren
Ollama installieren + Modell
Piper-Stimmen runterladen
config.yaml anpassen
briefly run
briefly serve

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Piper-Stimmen herunterladen
```bash
ollama serve
ollama pull qwen3:8b
```

Piper-Stimmen (`.onnx` + `.onnx.json`) werden nicht automatisch installiert.
Für Deutsch und Englisch (Standard-Konfiguration) ins konfigurierte
`voices_dir` (Default `data/voices/`) legen, z.B.:

```bash
mkdir -p data/voices
python -m piper.download_voices de_DE-thorsten-medium --data-dir data/voices
python -m piper.download_voices en_US-lessac-medium --data-dir data/voices
```

(Falls der Download-Befehl in deiner `piper-tts`-Version anders heißt: die
Modelle lassen sich auch manuell von den offiziellen Piper-Voice-Quellen
herunterladen und als `<voice-name>.onnx`/`.onnx.json` nach `data/voices/`
legen.)

### Konfiguration

```bash
cp config/config.example.yaml config.yaml
```

Danach `config.yaml` anpassen: Feeds, Themen, Zielsprache,
Segment-Reihenfolge – entweder direkt in der Datei oder später komfortabel
über die Web-Oberfläche unter `/settings`, `/feeds`, `/inbox`.

Für `delivery.base_url` die lokale IP des Macs im Heim-WLAN eintragen:

```bash
ipconfig getifaddr en0
```

## Nutzung

Pipeline manuell einmal komplett durchlaufen lassen:

```bash
briefly run
```

Einzelne Stufen (Briefing §2.7 – jede Stufe separat testbar):

```bash
briefly collect
briefly curate
briefly script
briefly audio
briefly deliver
```
(--to do: zu ergänzen: briefly setup & briefly doctor,briefly update, briefly run (einmalig setup alles und einmalig testen, um Eingaben zu minieren))


Web-Oberfläche starten (Eingaben/Einstellungen + Feed-Auslieferung):

```bash
uvicorn briefly.web.app:app --host 0.0.0.0 --port 8787
```

Danach von einem beliebigen Gerät im selben Heim-WLAN
`http://<mac-lan-ip>:8787` öffnen.

## Automatischer nächtlicher Lauf (launchd + pmset)

1. Mac so einstellen, dass er nachts aufwacht:

   ```bash
   sudo pmset repeat wakeorpoweron MTWRFSU 05:25:00
   ```

2. Platzhalter in den `scripts/launchd/*.plist`-Dateien ersetzen
   (`__PROJECT_DIR__` = absoluter Projektpfad, `__PYTHON_BIN__` = Pfad zum
   venv-Python, z.B. `which python` nach `source .venv/bin/activate`).

3. Installieren:

   ```bash
   cp scripts/launchd/com.briefly.dailyrun.plist ~/Library/LaunchAgents/
   cp scripts/launchd/com.briefly.web.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.briefly.dailyrun.plist
   launchctl load ~/Library/LaunchAgents/com.briefly.web.plist
   ```

Der Web-Server (`com.briefly.web`) läuft danach dauerhaft im Hintergrund und
ist im Heim-WLAN erreichbar; der nächtliche Lauf (`com.briefly.dailyrun`)
erzeugt jeden Morgen automatisch eine neue Episode.

## Wiedergabe auf Android Smartphone (AntennaPod)

1. [AntennaPod](https://antennapod.org/) installieren (F-Droid oder Play Store).
2. Im selben Heim-WLAN wie der Mac: Feed abonnieren unter
   `http://<mac-lan-ip>:8787/feed.xml`.
3. Neue Episoden erscheinen automatisch nach jedem nächtlichen Lauf, inkl.
   Kapitelmarken zum Springen zwischen Segmenten.

## Tests

```bash
pytest
```

Läuft auch ohne installiertes Ollama/Piper grün (Provider werden in den
Pipeline-Tests durch Test-Doubles ersetzt). `test_audio.py` überspringt sich
selbst, wenn `ffmpeg` nicht verfügbar ist.

## Architektur

Siehe [`CLAUDE.md`](./CLAUDE.md) für die Provider-Abstraktion und
Code-Stil-Regeln, sowie [`docs/concept/`](./docs/concept/) für die
ursprünglichen Konzeptdokumente (Briefing, Setup-Empfehlungen, Branding).
