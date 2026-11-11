"""Reine, seiteneffektfreie Rechenfunktionen.

Dieses Modul importiert bewusst kein Home Assistant, damit es ohne
gbootetes HA unit-testbar bleibt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

MAX_GAP_SECONDS = 300.0


@dataclass(frozen=True)
class Sample:
    """Ein Leistungsmesswert (Watt) zu einem Zeitpunkt (Epoch-Sekunden)."""

    ts: float
    w: float


def integrate(
    prev: Sample, sample: Sample, max_gap: float = MAX_GAP_SECONDS
) -> float | None:
    """Trapez-Integration zwischen zwei Samples, Ergebnis in Wh.

    Liefert None bei dt <= 0 oder einer Lücke > max_gap (keine Extrapolation).
    """
    dt = sample.ts - prev.ts
    if dt <= 0 or dt > max_gap:
        return None
    return (prev.w + sample.w) / 2.0 * dt / 3600.0


def split_grid(grid_feed_in_w: float) -> tuple[float, float]:
    """GridFeedIn_W in (Netzbezug_W, Einspeisung_W) aufteilen; beide >= 0.

    Vorzeichenkonvention der API: negativ = Netzbezug, positiv = Einspeisung.
    """
    if grid_feed_in_w < 0:
        return -grid_feed_in_w, 0.0
    return 0.0, grid_feed_in_w


def clamp_percent(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Wert auf [low, high] klemmen (Messdrift)."""
    return max(low, min(high, value))


def autarky_degree(grid_import_wh: float, consumption_wh: float) -> float:
    """Autarkiegrad in %: (1 - Bezug/Verbrauch) * 100.

    Verbrauch <= 0 -> 0 (Konvention).
    """
    if consumption_wh <= 0:
        return 0.0
    return clamp_percent((1.0 - grid_import_wh / consumption_wh) * 100.0)


def live_autarky(grid_feed_in_w: float, consumption_w: float) -> float:
    """Autarkiegrad aus Momentanleistungen in %."""
    grid_import_w, _ = split_grid(grid_feed_in_w)
    if consumption_w <= 0:
        return 0.0
    return clamp_percent((1.0 - grid_import_w / consumption_w) * 100.0)


def self_consumption_rate(feed_in_wh: float, production_wh: float) -> float:
    """Eigenverbrauchsquote in %: (1 - Einspeisung/Produktion) * 100."""
    if production_wh <= 0:
        return 0.0
    return clamp_percent((1.0 - feed_in_wh / production_wh) * 100.0)


def day_changed(prev_date: date, now: datetime) -> bool:
    """True, wenn das lokale Datum von now vom Vortag abweicht."""
    return prev_date != now.date()
