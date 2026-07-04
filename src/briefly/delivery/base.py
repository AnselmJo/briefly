"""DeliveryTarget-Schnittstelle (Briefing §4).

Bestimmt, wie die fertige Folge bereitgestellt wird.
"""

from __future__ import annotations

from typing import Protocol

from briefly.models import EpisodeManifest


class DeliveryTarget(Protocol):
    def publish(self, manifest: EpisodeManifest) -> None:
        """Macht eine fertige Episode auffindbar (z.B. Feed neu erzeugen)."""
        ...
