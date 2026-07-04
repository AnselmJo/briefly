"""Text-Preprocessing vor der Synthese mit Piper."""

from __future__ import annotations

import re


def preprocess_text(text: str) -> list[str]:
    """Bereitet den Text für die Sprachausgabe vor.

    Entfernt Markdown, HTML, Code-Blöcke, Tabellen, Überschriften und Bullets.
    Normalisiert Interpunktion und gibt eine Liste von Absätzen (Paragraphs) zurück.
    """
    # 1. HTML-Tags entfernen
    text = re.sub(r"<[^>]+>", "", text)

    # 2. Fenced Code-Blöcke entfernen (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # 3. Zeilenweise Verarbeitung
    lines = text.splitlines()
    paragraphs: list[str] = []
    current_para: list[str] = []

    def close_current_para():
        nonlocal current_para
        if current_para:
            paragraphs.append(" ".join(current_para))
            current_para = []

    for line in lines:
        stripped = line.strip()
        # Leere Zeilen schließen den aktuellen Absatz ab
        if not stripped:
            close_current_para()
            continue

        # Tabellen-Zeilen entfernen (jede Zeile mit '|')
        if "|" in stripped:
            close_current_para()
            continue

        # Überschriften entfernen (jede Zeile, die mit '#' beginnt)
        if stripped.startswith("#"):
            close_current_para()
            continue

        # Aufzählungspunkte (Bullets) erkennen und als eigenen Absatz behandeln
        # Erlaubt *, -, +, oder Zahlen gefolgt von Punkt/Klammer
        bullet_match = re.match(r"^\s*(?:[-*+]+|\d+[.)])\s+(.*)$", line)
        if bullet_match:
            close_current_para()
            paragraphs.append(bullet_match.group(1).strip())
            continue

        # Normaler Text
        current_para.append(stripped)

    close_current_para()

    # 4. Bereinigung der Absätze und Normalisierung der Formatierung/Interpunktion
    cleaned_paragraphs: list[str] = []
    for p in paragraphs:
        # Markdown-Formatierung entfernen (Bold, Italic, Strikethrough, Inline-Code)
        p = re.sub(r"(\*\*|__)(.*?)\1", r"\2", p)
        p = re.sub(r"(\*|_)(.*?)\1", r"\2", p)
        p = re.sub(r"~~(.*?)~~", r"\1", p)
        p = re.sub(r"`(.*?)`", r"\1", p)

        # Markdown-Links entfernen: [Text](URL) -> Text
        p = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p)

        # Blockquote-Präfixe entfernen
        p = re.sub(r"^\s*>\s*", "", p)

        # Interpunktion normalisieren
        p = (
            p.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
            .replace("„", '"')
        )
        p = p.replace("—", "-").replace("–", "-")

        # Mehrfache Satzzeichen normalisieren (z.B. ... zu ., oder !!! zu !)
        p = re.sub(r"\.{2,}", ".", p)
        p = re.sub(r"!+", "!", p)
        p = re.sub(r"\?+", "?", p)

        # Whitespace normalisieren
        p = re.sub(r"[ \t]+", " ", p).strip()

        if p:
            cleaned_paragraphs.append(p)

    return cleaned_paragraphs
