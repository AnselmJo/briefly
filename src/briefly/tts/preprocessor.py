"""Text-Preprocessing vor der Synthese mit Piper."""

from __future__ import annotations

import re


def strip_emojis(text: str) -> str:
    """Strips emojis and miscellaneous symbols from text."""
    pattern = re.compile(
        r"[\u2600-\u27bf]|[\u200d\uFE0F]|[\U00010000-\U0010ffff]",
        flags=re.UNICODE
    )
    return pattern.sub("", text)


def expand_abbreviations(text: str, language: str) -> str:
    """Expands common abbreviations per language to improve TTS quality."""
    lang = language.lower()

    if lang.startswith("de"):
        expansions = [
            (r"\bz\.\s*B\.", "zum Beispiel"),
            (r"\bd\.\s*h\.", "das heißt"),
            (r"\bu\.\s*a\.", "unter anderem"),
            (r"\bu\.ä\.", "und ähnliche"),
            (r"\betc\.", "und so weiter"),
            (r"\bbzw\.", "beziehungsweise"),
            (r"\bca\.", "zirka"),
            (r"\bbspw\.", "beispielsweise"),
            (r"\binkl\.", "inklusive"),
            (r"\bevtl\.", "eventuell"),
            (r"\bsog\.", "sogenannte"),
            (r"\bSt\.", "Sankt"),
            (r"\bDr\.", "Doktor"),
            (r"\bProf\.", "Professor"),
        ]
    else:
        expansions = [
            (r"\be\.\s*g\.", "for example"),
            (r"\bi\.\s*e\.", "that is"),
            (r"\betc\.", "and so on"),
            (r"\bvs\.", "versus"),
            (r"\bapprox\.", "approximately"),
            (r"\bmin\.", "minutes"),
            (r"\bhr\.", "hours"),
            (r"\bhrs\.", "hours"),
            (r"\bDr\.", "Doctor"),
            (r"\bMr\.", "Mister"),
            (r"\bMrs\.", "Missus"),
            (r"\bMs\.", "Miss"),
            (r"\bSt\.", "Saint"),
            (r"\bProf\.", "Professor"),
        ]

    for pattern, repl in expansions:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text


def preprocess_text(text: str, language: str = "en") -> list[str]:
    """Bereitet den Text für die Sprachausgabe vor.

    Entfernt Markdown, HTML, Code-Blöcke, Tabellen, Überschriften, Bullets und Emojis.
    Normalisiert Interpunktion und gibt eine Liste von Absätzen (Paragraphs) zurück.
    Erweitert gängige Abkürzungen sprachspezifisch.
    """
    text = strip_emojis(text)

    # HTML-Tags entfernen
    text = re.sub(r"<[^>]+>", "", text)

    # Fenced Code-Blöcke entfernen (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Zeilenweise Verarbeitung
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
        if not stripped:
            close_current_para()
            continue

        # Tabellen-Zeilen entfernen
        if "|" in stripped:
            close_current_para()
            continue

        # Überschriften entfernen
        if stripped.startswith("#"):
            close_current_para()
            continue

        # Bullets entfernen
        bullet_match = re.match(r"^\s*(?:[-*+]+|\d+[.)])\s+(.*)$", line)
        if bullet_match:
            close_current_para()
            paragraphs.append(bullet_match.group(1).strip())
            continue

        current_para.append(stripped)

    close_current_para()

    cleaned_paragraphs: list[str] = []
    for p in paragraphs:
        # Markdown-Formatierung entfernen
        p = re.sub(r"(\*\*|__)(.*?)\1", r"\2", p)
        p = re.sub(r"(\*|_)(.*?)\1", r"\2", p)
        p = re.sub(r"~~(.*?)~~", r"\1", p)
        p = re.sub(r"`(.*?)`", r"\1", p)

        # Markdown-Links entfernen
        p = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", p)

        # Blockquote-Präfixe entfernen
        p = re.sub(r"^\s*>\s*", "", p)

        # Abkürzungen erweitern
        p = expand_abbreviations(p, language)

        # Interpunktion normalisieren
        p = (
            p.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
            .replace("„", '"')
        )
        p = p.replace("—", "-").replace("–", "-")

        # Mehrfache Satzzeichen normalisieren
        p = re.sub(r"\.{2,}", ".", p)
        p = re.sub(r"!+", "!", p)
        p = re.sub(r"\?+", "?", p)

        # Leerzeichen vor Satzzeichen entfernen (z.B. nach Emoji-Entfernung)
        p = re.sub(r"\s+([.!?,;])", r"\1", p)

        p = re.sub(r"[ \t]+", " ", p).strip()

        if p:
            cleaned_paragraphs.append(p)

    return cleaned_paragraphs
