# Branding & Design-Konzept: Daily Cast

> Ziel: ein cleanes, einfaches, wiedererkennbares Erscheinungsbild mit
> auffälliger aber nicht überladener Farbgebung. Für MVP-Phase (Feed + kleine
> Web-Seite) und als Grundlage für die spätere App.

---

## 1. Namensempfehlung

Aus den in der Konzeptphase gesammelten Richtungen ist meine klare Empfehlung:

### **„Briefly"**

**Warum dieser Name gewinnt:**
- Sagt sofort, was das Produkt tut: kurz, kompakt, auf den Punkt – genau dein
  Kernversprechen (10 Minuten statt stundenlange Podcasts).
- Funktioniert international (Englisch), passt zu deiner Englisch-Standard-
  Ausgabesprache.
- Kurz, leicht zu merken, gut aussprechbar in mehreren Sprachen.
- Lässt sich gut visuell umsetzen (siehe §3).

**Alternative, falls „Briefly" als Marke/Domain nicht frei ist:** *Digest* –
ähnlich klar, etwas generischer, aber ebenfalls sofort verständlich.

**Wichtiger Hinweis:** Vor endgültiger Festlegung unbedingt selbst prüfen:
Domain-Verfügbarkeit (.app, .com), App-Store-Namenskollisionen, und ob der
Name in Deutschland/EU als Marke bereits belegt ist. Das kann ich für dich
recherchieren, sobald du dich für eine Richtung entschieden hast – eine
Markenprüfung sollte aber im Zweifel von einem Anwalt/Patentamt-Check
bestätigt werden, bevor du kommerziell damit arbeitest.

---

## 2. Positionierung in einem Satz

> „Briefly – deine Themen, kurz und persönlich gesprochen, jeden Morgen."

Diese Kurzformel eignet sich als Tagline für Store-Eintrag, Landingpage-Header
und die Startseite der künftigen App.

---

## 3. Visuelle Identität

### Grundprinzip
Du hast „clean, einfach, mit fertigem Baukasten, aber starke, wiedererkennbare
Farbgebung, nicht zu bunt" gewünscht. Die richtige Formel dafür: **eine
dominante Akzentfarbe auf neutralem Hintergrund**, nicht mehrere bunte
Farben nebeneinander. Das ist zugleich der aktuelle Standard bei ernstzunehmenden
Audio-/Produktivitäts-Apps (ruhige Basis, ein "Marken-Blitz").

### Farbpalette (Vorschlag)

**Primärfarbe – ein warmes, aber kräftiges Orange-Koralle:**
`#FF5A36` (Arbeitsname: „Signal")
- Grund: Orange/Koralle wirkt energetisch-morgendlich (Sonnenaufgang-
  Assoziation, passend zu einem Morgen-Ritual), ohne so ausgelutscht zu sein
  wie Blau (Tech-Standard) oder so aggressiv wie reines Rot.
- Funktioniert exzellent als einzelner Akzent auf Weiß/Dunkel – genau dein
  "eine starke Farbe, nicht zu bunt"-Wunsch.

**Neutrale Basis:**
- Hell-Modus Hintergrund: `#FAFAF8` (warmes Off-White, kein reines Weiß –
  wirkt weniger klinisch)
- Dunkel-Modus Hintergrund: `#141414` (warmes Schwarz statt reinem #000000)
- Text: `#1A1A1A` (hell) / `#F2F2F0` (dunkel)

**Eine einzige Sekundärfarbe** (für z.B. Erfolgsmeldungen/aktive Zustände,
sparsam einsetzen):
- Tiefes Petrol/Grün `#0F5C52` – kühler Gegenpol zum warmen Orange, wirkt
  ruhig und vertrauenswürdig (typische Assoziation: Fokus, Wissen), ohne mit
  dem Hauptakzent zu konkurrieren.

**Bewusst NICHT verwenden:** mehr als diese zwei Akzentfarben. Kein
Regenbogen-Gradient, keine dritte "Spaß-Farbe". Genau das hältst du selbst
für wichtig, und es ist auch der Unterschied zwischen "wiedererkennbare Marke"
und "beliebige bunte App".

### Typografie
- Eine klare, moderne Sans-Serif als Haupt-Schrift (z.B. Inter oder ähnliche
  gut lesbare, kostenlose Systemschrift) – bei Audio-Apps zählt vor allem
  Lesbarkeit auf kleinen Screens, keine verspielte Display-Schrift nötig.
- Nur zwei Schriftschnitte konsequent nutzen: ein kräftiges Gewicht für
  Titel/Kapitel, ein reguläres für Fließtext/Beschreibungen.

### Symbol/Icon-Idee
Ein einfaches, geometrisches Icon-Motiv: eine stilisierte **Schallwelle, die
sich zu einer Sonne/einem Strahlenkranz formt** – verbindet "Audio" mit
"Morgen/Start in den Tag", ohne kitschig zu werden. Als Kreis, nicht mehr als
zwei Formen, funktioniert in Orange auf hellem und dunklem Grund gleich gut.

---

## 4. UI-Baukasten-Empfehlung

Du hast explizit einen fertigen Library-Baukasten gewünscht statt komplett
eigenem Design-System – das ist für dein Tempo und deine Nicht-Entwickler-
Rolle die richtige Wahl.

**Empfehlung für die Web-/App-Oberfläche:** ein Utility-first-CSS-Ansatz
(Tailwind-Klassen) kombiniert mit einem fertigen, aktiv gepflegten
Komponentenkasten (z.B. shadcn/ui-artige Bausteine: Buttons, Cards, Switches,
Listen) – das liefert bereits saubere, moderne Standardkomponenten, auf die du
nur deine zwei Marken-Farben und die Typografie legst. Genau der Mix aus
"clean, einfach, aber trotzdem wiedererkennbar", den du beschrieben hast.

**Für die MVP-Phase (Feed + kleine Einstell-Oberfläche) reicht das völlig.**
Ein aufwendiges individuelles Interface lohnt sich erst, wenn die Handy-App
ansteht.

### Grundlayout-Prinzip für die künftige App
- **Eine Hauptfarbe pro Bildschirm-Zustand:** neutrale Basis dominiert, Orange
  taucht gezielt an 1-2 Stellen auf (z.B. Play-Button, aktives Kapitel,
  Primär-Aktion) – nicht flächig.
- **Große, ruhige Flächen statt vieler kleiner Elemente** – passt zum
  "Morgens beim Dehnen, kurz reinschauen"-Nutzungskontext; die App wird
  meist im Vorbeigehen bedient, nicht lange betrachtet.
- **Kapitelliste als zentrales Element** des Player-Screens – das ist dein
  wichtigstes funktionales Alleinstellungsmerkmal (Springen zwischen
  Segmenten), sollte visuell entsprechend Raum bekommen, nicht versteckt sein.

---

## 5. Wie du das jetzt konkret nutzt

1. Für den MVP (RSS-Feed + evtl. eine simple Info-Seite) reicht: Name
   „Briefly", die zwei Farben, eine Systemschrift. Kein Aufwand für eigenes
   Icon-Design nötig – ein einfaches Text-Wortmarke-Logo in der Primärfarbe
   genügt fürs Erste.
2. Sobald es an die Web-Oberfläche geht (Phase 2+), das Farbschema + den
   Tailwind/Komponenten-Ansatz aus §4 als Vorgabe an Claude Fable
   weitergeben.
3. Für die spätere Handy-App: dasselbe Farb-/Typografie-System 1:1
   übernehmen – Wiedererkennbarkeit entsteht gerade dadurch, dass sich am
   visuellen Kern über die Phasen hinweg nichts ändert, nur die Oberfläche
   wächst.

---

## 6. Offene Entscheidung für dich

- Gefällt dir „Briefly" als Arbeitstitel, oder soll ich 2-3 weitere,
  engere Namensvarianten mit Verfügbarkeitscheck (Domain/Store) recherchieren?
- Passt die Orange/Petrol-Kombination zu deinem Geschmack, oder ziehst du
  eine andere Grundfarbrichtung vor (z.B. ruhigeres Blau/Grün statt der
  energetischen Orange-Note)?
