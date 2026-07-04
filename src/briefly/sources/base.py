"""ContentSource-Schnittstelle (Briefing §4).

Gemeinsames Protocol für alle Sammler-Module (Inbox, RSS, später
Kalender/Events). Jede Quelle liefert eine Liste normalisierter Items
(siehe `briefly.models.Item`).
"""

from __future__ import annotations

from typing import Protocol

from briefly.models import Item


class ContentSource(Protocol):
    def fetch(self) -> list[Item]:
        """Liefert die aktuell verfügbaren Items dieser Quelle.

        Darf bei einem Ausfall (Netzwerk, fehlender Ordner) keine Exception
        nach außen werfen, sondern soll intern loggen und eine leere Liste
        zurückgeben (Briefing §2.5 Fehlertoleranz) – der Aufrufer in
        `pipeline.py` behandelt jede Quelle unabhängig.
        """
        ...
