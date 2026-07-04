# Projekt-Briefing für Claude Fable: "Daily Cast" MVP

> Dieses Dokument ist die vollständige Übergabe an Claude Fable zur Umsetzung.
> Es beschreibt Ziel, Kontext, Architektur-Leitplanken und bewusst offene
> Entscheidungen. Claude Fable soll daraus lauffähigen, wartbaren Code bauen.

---

## 1. Was hier entstehen soll (Zusammenfassung für Claude)

Ich baue ein **persönliches tägliches Audio-Briefing-System** ("Daily Cast").
Jeden Morgen entsteht automatisch eine kurze, gesprochene Audiofolge (Ziel:
~10 Minuten), die aus mehreren Quellen kuratiert wird:

- aktuelle Nachrichten (RSS/offene APIs, z.B. Tagesschau),
- Wissens-Inhalte zu festgelegten Interessens-Themen,
- eigene Eingaben des Nutzers ("Inbox": Buchnotizen, Gedanken, Links),
- optional (nicht MVP): Geburtstage aus einem Kalender-Link, geplante
  Themen-Blöcke für bestimmte Tage.

Ein lokales LLM schreibt daraus ein Sprech-Skript, eine lokale
Text-to-Speech-Engine erzeugt daraus eine Audiodatei mit Kapitelmarken. Die
Datei wird über einen einfachen RSS-Feed ausgeliefert, den man in jeder
Podcast-App abonnieren kann.

**Zielgruppe MVP:** ich selbst, plus ein paar Freunde/Familie, die es kostenlos
mitnutzen können. **Langfristiges Ziel** (nicht jetzt bauen, aber die
Architektur soll es nicht verbauen): ein Produkt mit Cloud-Option und später
evtl. einem kleinen Abo für fremde Nutzer.

---

## 2. Nicht-funktionale Leitplanken (bitte strikt einhalten)

1. **Einfachheit vor Cleverness.** Der Code muss auch von mir (Data Analyst,
   sehr sattelfest in SQL, kein Vollzeit-Softwareentwickler) verstanden und
   gewartet werden können. Lieber ein klar lesbares 20-Zeilen-Modul als eine
   raffinierte 5-Zeilen-Abstraktion. Bei jeder Design-Entscheidung: die
   verständlichere Variante gewinnt, sofern sie nicht grob ineffizient ist.
2. **Nur etablierte, aktiv gepflegte Open-Source-Bibliotheken.** Keine
   Experimental-Projekte mit wenigen Contributors oder seit Monaten
   inaktiven Repos. Bevorzugt: offizielle SDKs der jeweiligen Anbieter (z.B.
   das offizielle `ollama` Python-Paket), Standard-Bibliotheken mit breiter
   Verbreitung (z.B. `feedparser`, `httpx`, `pydantic`). Ziel: minimaler
   Wartungsaufwand über Jahre, keine Abhängigkeits-Ruinen.
3. **Modularität nach Provider-Prinzip** (Details in §4). Das ist die
   wichtigste strukturelle Vorgabe.
4. **Konfiguration statt Hardcoding.** Alles, was ich als Nutzer anpasse
   (Themen, Feeds, Sprache, Zeiten), lebt in einer Konfigurationsdatei
   (YAML), nie im Code.
5. **Fehlertoleranz.** Fällt eine Quelle aus (Feed nicht erreichbar, Kalender
   nicht ladbar), soll die Pipeline trotzdem eine Folge produzieren – nur
   ohne das betroffene Segment. Kein Totalausfall wegen einer einzelnen
   Quelle.
6. **Kein stiller Datenabfluss.** Alles läuft lokal auf meinem Mac (Apple
   Silicon M4). Keine Cloud-Aufrufe im MVP, außer denen, die ich explizit
   für Quellen (RSS/APIs) vorgesehen habe.
7. **Testbarkeit pro Pipeline-Stufe.** Jede Stufe (Sammeln, Kuratieren,
   Skript, Audio, Ausliefern) soll einzeln aufrufbar/testbar sein, nicht nur
   als ein monolithischer Lauf.
8. **Deutscher Code-Kommentarstil, englische Bezeichner** (siehe §7 für
   meinen genauen Stil).

---

## 3. Funktionsumfang MVP (genau das, nicht mehr)

**Im MVP enthalten:**
- Pipeline: Sammeln → Kuratieren → Skript schreiben → Audio erzeugen →
  Ausliefern.
- Zwei Quellen: (a) eine lokale **Inbox** aus Textdateien in einem Ordner,
  durch `---`-Trennlinien in einzelne Einträge zerlegt, optional mit
  einfachen Tags (`#thema:`, `#prio:`); (b) **RSS-Feeds** (mehrere URLs aus
  Konfig) plus optional die offene Tagesschau-API als Beispielquelle.
- **Vorgefertigte Interessens-Kategorien** in der Konfig (Liste, siehe
  Konzeptdokumente), nach denen kuratiert und gewichtet wird.
- **Ausschluss-Filter** (Themen/Stichwörter, die nie vorkommen sollen, z.B.
  Krieg/Kriminalität/Katastrophen als Default).
- **Sprachlogik:** Eingabematerial darf gemischt Deutsch/Englisch sein, das
  LLM erkennt die Sprache selbst und schreibt das Ausgabeskript konsequent in
  einer konfigurierten Zielsprache (Standard: Englisch).
- Lokales LLM via **Ollama** erzeugt das Sprechtext-Skript inkl. markierter
  Segmentgrenzen (für spätere Kapitelmarken).
- Lokales TTS erzeugt daraus eine Audiodatei.
- Audiodatei bekommt **eingebettete Kapitelmarken** (Format M4A/M4B), damit
  Podcast-Apps eine Kapitelliste anzeigen und Springen erlauben.
- Ein minimaler **RSS-Feed** (XML-Datei) wird generiert/aktualisiert, der auf
  die Audiodatei verweist, ausgeliefert über einen simplen lokalen
  Webserver im Heimnetz.
- Geplanter nächtlicher Lauf (macOS: `launchd` + `pmset` zum Wecken).
- Lauftext jeder Folge wird zusätzlich als Textdatei abgelegt (Nachvollzug,
  Debugging).

**Bewusst NICHT im MVP** (Architektur soll es aber nicht verbauen):
- Cloud-Provider für LLM/TTS (nur die Schnittstelle vorsehen, siehe §4).
- Geburtstage/Kalender-Anbindung.
- Tagesspezifische geplante Themen-Blöcke.
- Web-Scraping von Event-Seiten/lokalen News.
- Web-Oberfläche, Nutzerkonten, Mehrnutzer-Fähigkeit.
- Handy-App.
- Bezahlung/Abo.

---

## 4. Architektur-Vorgabe: Provider-Abstraktion (wichtigster Punkt)

Der Kern der Anwendung darf **nie** direkt einen konkreten Dienst ansprechen
(kein `import ollama` mitten in der Kuratierungslogik). Stattdessen: neutrale
Schnittstellen (z.B. als `Protocol`/abstrakte Basisklasse), für die es je eine
lokale Implementierung gibt. Cloud-Implementierungen kommen später hinzu, ohne
den Kern zu verändern.

Schnittstellen, die ich für sinnvoll halte (Claude Fable darf das im Detail
verfeinern):
- `LanguageModelProvider` – Sprechtext aus kuratiertem Material erzeugen.
  MVP-Implementierung: Ollama lokal.
- `SpeechSynthesisProvider` – Text zu Audiodatei. MVP-Implementierung: ein
  lokales TTS-System.
- `ContentSource` – gemeinsame Schnittstelle für alle Sammler-Module (Inbox,
  RSS, später Kalender/Events). Jede Quelle liefert eine Liste normalisierter
  Items mit gemeinsamer Struktur (z.B. Titel, Inhalt, Kategorie, Quelle,
  Sprache, Priorität).
- `DeliveryTarget` – wie die fertige Folge bereitgestellt wird. MVP:
  lokaler Ordner + RSS-XML-Datei.

**Warum das nicht-verhandelbar ist:** Es ist die Grundlage für die spätere
Cloud-Option und für Mehrnutzer-Fähigkeit. Wenn diese Trennung fehlt, muss
später alles neu geschrieben werden.

---

## 5. Themen-Segmentierung (wichtige Detail-Anforderung)

Bei der Inbox muss klar erkennbar sein, wann ein Thema aufhört und ein neues
anfängt. Lösung: Einträge werden durch eine Zeile mit exakt `---` getrennt.
Optional kann jeder Eintrag einen kleinen Kopf mit `#thema:` und `#prio:`
haben; fehlt er, wird der Eintrag trotzdem verarbeitet (nur ohne Vorrang).
Bitte robust parsen (fehlende/leere Einträge überspringen, keine Abstürze bei
unerwartetem Format).

---

## 6. Reihenfolge / Aufbau der Folge

Die Folge besteht aus benannten Segmenten in konfigurierbarer Reihenfolge
("Profil"), z.B.: Intro → aktuelle News → Themen/Inbox → Outro. Das Profil ist
Teil der Konfiguration, nicht hartkodiert. Auch wenn Geburtstage im MVP nicht
implementiert werden: die Segment-Reihenfolge muss so gebaut sein, dass ein
zukünftiges "Geburtstage"-Segment einfach ans Ende eines Profils gehängt
werden kann, ohne die Pipeline umzubauen.

---

## 7. Code-Stil-Vorgaben

Für SQL, das ich selbst schreibe, gelten bei mir diese Konventionen (zur
Orientierung, wie ich generell über Lesbarkeit denke – für den Python-Code
bitte sinngemäß PEP 8 + folgende Prinzipien anwenden):
- klar, kompakt, links ausgerichtet, konsistente Einrückung,
- sprechende, englische Bezeichner,
- Kommentare auf Deutsch, stichpunktartig, dort wo sie wirklich Kontext
  liefern (nicht Trivialkommentare wie `# Variable setzen`),
- keine Blockkommentare, keine überflüssige Verschachtelung,
- lieber mehrere kleine, klar benannte Funktionen als eine große.

Für den Python-Code konkret: Type Hints verwenden, `pydantic` (oder
Dataclasses, wo `pydantic` überdimensioniert wäre) für strukturierte Daten,
`pathlib` statt String-Pfadverkettung, Logging statt `print` für alles außer
der lokalen CLI-Ausgabe während der Entwicklung.

---

## 8. Empfohlener Tech-Stack (Vorschlag, Claude Fable darf begründet abweichen)

- **Sprache:** Python (aktuelle stabile Version).
- **LLM lokal:** Ollama, angesprochen über das offizielle `ollama`
  Python-Paket (nicht raw HTTP-Calls selbst bauen – das SDK ist offiziell
  gepflegt und deckt Streaming/Async bereits ab).
- **TTS lokal:** ein aktuell gut unterstütztes lokales TTS-System mit
  brauchbarer deutscher/englischer Stimme (Claude Fable soll hier recherchieren,
  was aktuell die robusteste, aktiv gepflegte Option ist – siehe §9,
  offene Entscheidung).
- **RSS parsen:** `feedparser` (Standard, seit Jahren stabil).
- **Konfiguration:** YAML (`pyyaml`) + `pydantic` zur Validierung.
- **Audio-Nachbearbeitung/Kapitelmarken:** `ffmpeg` (extern) angesteuert über
  Subprocess oder ein schlankes Wrapper-Paket.
- **Scheduling MVP:** systemeigene Mittel (`launchd`/`pmset`), kein
  zusätzliches Framework nötig für einen einzelnen täglichen Lauf.

---

## 9. Bewusst offene Entscheidungen für Claude Fable

Diese Punkte will ich **nicht** vorab festlegen – Claude Fable soll hier eine
begründete Wahl treffen und die Begründung kurz dokumentieren:

1. **Welches lokale TTS-System** aktuell am robustesten/langfristig am besten
   gepflegt ist (Qualität deutsch+englisch, Aktivität des Projekts,
   Installationsaufwand auf macOS/Apple Silicon).
2. **Welches Ollama-Modell** als Default in der Konfiguration hinterlegt wird
   (Abwägung Qualität vs. Geschwindigkeit auf M4).
3. **Exaktes Datenformat** der normalisierten Items zwischen den
   Pipeline-Stufen (Feldnamen, Pflicht-/Optionalfelder) – Vorschlag machen,
   an obiger Struktur orientieren.
4. **Wie Kapitelgrenzen technisch markiert werden** (z.B. Marker-Tokens im
   LLM-Output vs. getrennte TTS-Aufrufe pro Segment mit anschließendem
   Zusammenfügen) – beide Wege sind valide, Vorschlag mit Begründung.
5. **Projektstruktur/Ordnerlayout** im Detail (Vorschlag aus dem
   Konzeptdokument vorhanden, darf verfeinert werden).
6. **Testing-Ansatz** (welches Test-Framework, wie viel Testabdeckung für
   einen MVP dieser Größe sinnvoll ist).

---

## 10. Was aus den Konzept-Vorgesprächen NICHT mehr gilt

Frühere Konzeptrunden haben auch Cloud-Infrastruktur, Supabase/n8n,
Mehrnutzer-Login, Geburtstage, Web-Scraping und eine Handy-App diskutiert.
**Für diesen Bauauftrag gilt nur der Umfang aus §3.** Die anderen Themen sind
bewusst spätere Phasen und sollen den MVP nicht verkomplizieren – die
Provider-Abstraktion aus §4 ist der einzige Ort, an dem diese Zukunft
vorbereitet wird.

---

## 11. Definition of Done für diesen Bauauftrag

- Ich kann das Projekt lokal auf meinem Mac M4 installieren (Anleitung
  vorhanden) und einmal manuell durchlaufen lassen.
- Ergebnis ist eine Audiodatei mit Kapitelmarken plus ein aktualisierter
  RSS-Feed, den ich in einer Podcast-App abonnieren kann.
- Fällt eine konfigurierte Quelle aus, läuft die Pipeline trotzdem durch.
- Die Konfigurationsdatei allein genügt, um Themen, Feeds, Sprache und
  Segmentreihenfolge zu ändern – ohne Code anzufassen.
- Kurze README mit Setup-Schritten und Erklärung der Konfiguration.
