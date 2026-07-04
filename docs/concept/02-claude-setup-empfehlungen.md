# Claude-Setup-Empfehlungen für das Daily-Cast-Projekt

> Ziel: Wie du Claude (insbesondere Claude Fable / Claude Code) für dieses
> Projekt am effektivsten einsetzt – über den reinen Chat hinaus. Basierend
> auf aktuell empfohlenen Praktiken (Stand: Recherche Juli 2026).

---

## 1. Die wichtigste einzelne Maßnahme: eine gute CLAUDE.md

Bevor irgendwelche Skills oder Tools ins Spiel kommen: Lege im Projekt-Root
eine `CLAUDE.md` an. Das ist die Datei, die Claude Code bei **jeder** Sitzung
automatisch lädt – sie ersetzt das wiederholte Erklären deines Projekts.

**Was hinein gehört (Faustregel: unter 150-200 Zeilen, sonst leidet die
Genauigkeit):**
- ein Absatz Projektzusammenfassung (was Daily Cast ist),
- Tech-Stack (Python, Ollama, lokales TTS, ffmpeg),
- die genauen Befehle: wie man testet, startet, linted – das ist laut
  aktuellen Best-Practice-Quellen der Abschnitt mit dem größten Nutzen pro
  Zeile,
- deine Code-Stil-Regeln (siehe Briefing-Dokument, §7),
- die Provider-Abstraktions-Regel als **hartes** Architekturprinzip,
- Verweis auf Detaildokumente statt alles reinzukopieren (z.B.
  `@docs/architecture.md`) – das hält die Datei schlank.

**Was NICHT hinein gehört:** Stilregeln, die ein Linter/Formatter ohnehin
automatisch durchsetzt (z.B. Einrückung) – dafür lieber `black`/`ruff`
konfigurieren, das ist zuverlässiger und günstiger als es dem Modell jedes
Mal neu zu erklären.

**Praktischer erster Schritt:** In Claude Code den Befehl `/init` ausführen –
das scannt dein Projekt und erzeugt eine Start-CLAUDE.md, die du danach
gezielt um die Punkte oben ergänzt.

---

## 2. Workflow-Empfehlung: Explore → Plan → Implement → Commit

Anthropics eigene Empfehlung, und in der Praxis der wirksamste Hebel gegen
"Claude baut einfach drauflos und trifft stille Fehlannahmen":

1. **Explore:** Claude bitten, sich die relevanten Dateien/das Konzept
   anzusehen und in eigenen Worten zusammenzufassen, bevor irgendetwas
   geschrieben wird.
2. **Plan:** den sogenannten Plan-Modus nutzen (in Claude Code per Tastenkürzel
   umschaltbar) – Claude schlägt einen Plan vor, du reviewst ihn, bevor Code
   entsteht.
3. **Implement:** erst dann umsetzen lassen.
4. **Commit:** kleine, nachvollziehbare Schritte statt eines Riesen-Commits.

Für dein Projekt konkret: Lass Claude Fable die Pipeline-Architektur (die
Provider-Schnittstellen aus dem Briefing) zuerst als Plan/Skizze vorlegen,
bevor der erste Code entsteht. Das ist genau die Stelle, an der sich ein
Architekturfehler am billigsten korrigieren lässt.

---

## 3. Skills, die für dieses Projekt konkret sinnvoll sind

Skills sind Ordner mit einer `SKILL.md`, die Claude automatisch lädt, wenn sie
zur Aufgabe passen (nur ~100 Tokens Overhead pro Skill, solange er nicht
gebraucht wird – das macht es günstig, mehrere gleichzeitig bereitzuhalten).

**Bereits in deinem System vorhanden (nutzen, nicht neu bauen):**
- `docx`/`pdf`/`pptx`/`xlsx` – falls du das Konzept oder die Doku noch als
  Word/PDF aufbereiten willst.
- `frontend-design` – sobald es an die Web-Oberfläche/App-UI geht (Phase 2+).
- `skill-creator` – um dir selbst projektspezifische Skills zu bauen (siehe
  unten, eigene Skills lohnen sich hier konkret).

**Empfehlenswerte community-/Anthropic-Skills, die du für dieses Projekt
zusätzlich installieren solltest:**

| Skill / Repo | Nutzen für Daily Cast |
|---|---|
| **`systematic-debugging`** (aus `awesome-claude-skills`) | Strukturierte Fehlersuche, bevor Claude vorschnell "Fixes" vorschlägt – nützlich bei Audio-/Pipeline-Bugs, die selten offensichtlich sind. |
| **Karpathy-Verhaltens-Skill** (z.B. `multica-ai/andrej-karpathy-skills`) | Ein einzelnes, extrem verbreitetes Verhaltens-Skill (über 100k Stars) gegen die drei häufigsten Agenten-Fehler: stille Fehlannahmen, Über-Engineering (50 Zeilen werden zu 500), und Änderungen an Code, der gar nicht angefasst werden sollte. Passt exakt zu deiner "Einfachheit vor Cleverness"-Vorgabe. |
| **`webapp-testing`** (Playwright-basiert, aus `awesome-claude-skills`) | Sobald es eine Web-Oberfläche gibt (Phase 2+), zum automatisierten Testen. |
| **`varlock-claude-skill`** oder vergleichbares Secret-Management-Skill | Stellt sicher, dass API-Keys (sobald Cloud-Provider dazukommen) nie versehentlich in Chats, Logs oder Commits landen. Für dich relevant, sobald du über die reine lokale Variante hinausgehst. |

**Eigene Skills, die sich für DICH konkret lohnen würden** (du hast bereits
gezeigt, dass du das für andere Projekte tust – z.B. deine
`context-file-creator`- und `dashboarding-devexpress-xml`-Skills):
- Ein `daily-cast-pipeline`-Skill, der die Provider-Abstraktion, die
  Datenformate zwischen Pipeline-Stufen und deine Konventionen aus dem
  Briefing-Dokument festhält – damit jede neue Claude-Sitzung sofort im Bild
  ist, ohne dass du das Konzeptdokument erneut komplett einfügen musst.
- Ein `audio-chapter-format`-Skill, sobald die Kapitelmarken-Logik steht, der
  festhält, wie/wo Kapitel technisch markiert werden – spart dir das
  Wiedererklären bei jeder Änderung an der Audio-Stufe.

Baue diese am besten mit dem **Skill Creator** (interaktive Q&A, erzeugt
korrekte `SKILL.md`-Struktur) statt von Hand.

---

## 4. Subagents – für dieses Projekt (noch) optional

Subagents sind eigenständige Agenten mit begrenztem Werkzeugzugriff für klar
abgegrenzte Aufgaben. Für ein Solo-MVP-Projekt deiner Größe ist das (noch)
nicht nötig – der Rat aus der aktuellen Praxis-Literatur ist ausdrücklich,
erst simpel zu starten ("surprisingly vanilla") und Komplexität nur bei
echtem Bedarf hinzuzufügen. Relevant würde das, sobald du parallel an
mehreren unabhängigen Teilen arbeitest (z.B. Pipeline-Kern und Web-UI
gleichzeitig) – dann lohnt ein Subagent pro Bereich.

---

## 5. Hooks – eine konkrete Empfehlung

Hooks sind Automatismen, die vor/nach bestimmten Aktionen laufen (z.B. "vor
jedem Schreiben prüfen, ob Secrets im Diff sind"). Für dein Projekt besonders
sinnvoll, sobald Cloud-API-Keys ins Spiel kommen:
- ein **"block-secrets"-Hook**, der verhindert, dass ein API-Key versehentlich
  committed wird. Mehrere fertige, kleine Hook-Skripte dafür sind in den
  oben verlinkten Repos verfügbar und müssen nicht selbst geschrieben werden.

Für den MVP (rein lokal, keine Keys) ist das noch nicht kritisch, aber genau
der richtige Zeitpunkt, es *vorzubereiten*, ist beim Übergang zur
Cloud-Provider-Implementierung.

---

## 6. MCP-Server – was für dieses Projekt Sinn ergibt

MCP verbindet Claude mit echten externen Diensten. Für dieses Projekt aktuell
relevant:
- **Google Drive** (bereits bei dir verbunden) – falls Konzept-/Briefing-Dokumente
  zentral abgelegt werden sollen, statt nur im Chat.
- **GitHub** – sobald der Code in einem Repository liegt, damit Claude direkt
  Issues/PRs lesen und schreiben kann, statt Code nur im Chat hin- und
  herzukopieren. Das ist der Punkt, an dem sich für dich der Umstieg von
  "Chat mit Copy-Paste" zu einem echten Repo am meisten auszahlt.
- MCP für Kalender wird erst relevant, sobald die Geburtstags-Anbindung (spätere
  Phase) ansteht.

Kein MCP-Server nötig für Ollama/lokales TTS – das sind lokale Prozesse, die
der Code direkt anspricht.

---

## 7. Token-Effizienz / Kosten-Praktiken

- **Skills statt langer Prompts.** Jede Wiederholung eines Setups im Chat
  kostet Tokens; ein einmal geschriebener Skill lädt nur bei Bedarf (~100
  Tokens Overhead, wenn er nicht gebraucht wird).
- **CLAUDE.md schlank halten**, Details in verlinkte Dateien auslagern
  (`@docs/...`) statt alles in die immer geladene Datei zu packen –
  aktuelle Analysen zeigen einen messbaren Genauigkeitsabfall, wenn die
  Datei zu lang wird und der Kontext insgesamt "vollläuft".
- **`/clear` zwischen unabhängigen Aufgaben.** Wenn du von "Pipeline-Architektur
  besprechen" zu "Audio-Kapitelmarken debuggen" wechselst, Kontext leeren
  statt alles mitzuschleppen – ein frischer Start mit priorisiertem Prompt
  schlägt oft eine lange Sitzung voller Fehlversuche.
- **Scope eng halten.** Statt "schau dir das ganze Projekt an", gezielt die
  relevanten Dateien/Abschnitte referenzieren.
- **Bei wiederholten Fehlschlägen nicht nachkorrigieren, sondern neu
  starten** mit einem präziseren Prompt, der das Gelernte einbaut.

---

## 8. Sicherheits-Hinweis zu Community-Skills

Skills können Code ausführen. Vor dem Installieren eines Community-Skills
(insbesondere von kleineren/unbekannten Autoren) kurz prüfen: Sendet er Daten
extern? Braucht er Zugangsdaten? Die größeren, oben genannten Repos
(Anthropic selbst, `awesome-claude-code`/`awesome-claude-skills` mit hoher
Stern-Zahl und aktiver Pflege) sind ein vernünftiger Vertrauens-Anker; bei
Nischen-Skills lohnt ein kurzer Blick in die `SKILL.md`, bevor sie aktiv
geschaltet werden.

---

## 9. Konkrete Einkaufsliste für den Projektstart

1. `CLAUDE.md` im Projekt-Root anlegen (Basis aus `/init`, dann verfeinern
   mit den Punkten aus §1 und dem Briefing-Dokument).
2. Karpathy-Verhaltens-Skill installieren (Anti-Über-Engineering, passt zu
   deiner "Einfachheit"-Vorgabe).
3. `systematic-debugging`-Skill installieren.
4. Eigenen `daily-cast-pipeline`-Skill mit dem Skill Creator bauen, sobald die
   Provider-Schnittstellen feststehen (nicht vorher – sonst schreibst du ihn
   zweimal).
5. Projekt in ein Git-Repository überführen, sobald erster Code steht – dann
   GitHub-MCP anbinden.
6. Sobald ein Cloud-Provider hinzukommt: `block-secrets`-Hook einrichten.

Diese Reihenfolge hält den Anfangsaufwand klein und fügt jede zusätzliche
Automatisierung erst dann hinzu, wenn sie einen echten, aktuellen Bedarf löst
– passend zu deinem eigenen Wunsch nach "so einfach wie möglich, aber
zuverlässig".
