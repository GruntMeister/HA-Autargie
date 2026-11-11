"""Sonnen Autarky - Tages-Autarkie aus den Sensoren der bestehenden
sonnenBatterie-Integration (Variante A: kein eigenes API-Polling)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .calc import (
    Sample,
    autarky_degree,
    day_changed,
    integrate,
    self_consumption_rate,
    split_grid,
)
from .const import (
    CONF_CONSUMPTION_ENTITY,
    CONF_GRID_FEED_IN_ENTITY,
    CONF_PRODUCTION_ENTITY,
    COUNTER_CONSUMPTION,
    COUNTER_GRID_EXPORT,
    COUNTER_GRID_IMPORT,
    COUNTER_PRODUCTION,
    COUNTERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FIELD_CONSUMPTION_W,
    FIELD_GRID_FEED_IN_W,
    FIELD_PRODUCTION_W,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


def _scan_interval(entry: ConfigEntry) -> int:
    return int(
        entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    )


def resolve_serial_number(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Seriennummer über Geräte-Registry der Quell-Entities auflösen."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    reg_entry = entity_registry.async_get(entry.data[CONF_CONSUMPTION_ENTITY])
    device_id = reg_entry.device_id if reg_entry else None
    if device_id:
        device = device_registry.async_get(device_id)
        if device is not None:
            return str(device.serial_number or device.name or device_id)
    return str(entry.data[CONF_CONSUMPTION_ENTITY])


class SonnenAutarkyCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Liest die Watt-Sensoren der sonnenBatterie-Integration und akkumuliert
    die Tageszähler (Wh)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=_scan_interval(entry)),
        )
        self.entry = entry
        self.serial_number = resolve_serial_number(hass, entry)
        self.counters_wh: dict[str, float] = {key: 0.0 for key in COUNTERS}
        self.last_period_wh: dict[str, float] = {key: 0.0 for key in COUNTERS}
        self.prev_samples: dict[str, Sample] = {}
        self.current_date: date | None = None
        self.last_reset: datetime | None = None

    def _read_watt(self, entity_id: str) -> float:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            raise UpdateFailed(f"Quell-Sensor {entity_id} nicht verfügbar")
        try:
            return float(state.state)
        except ValueError as err:
            raise UpdateFailed(
                f"Quell-Sensor {entity_id} nicht numerisch: {state.state}"
            ) from err

    async def _async_update_data(self) -> dict[str, float]:
        status = {
            FIELD_CONSUMPTION_W: self._read_watt(
                self.entry.data[CONF_CONSUMPTION_ENTITY]
            ),
            FIELD_GRID_FEED_IN_W: self._read_watt(
                self.entry.data[CONF_GRID_FEED_IN_ENTITY]
            ),
            FIELD_PRODUCTION_W: self._read_watt(
                self.entry.data[CONF_PRODUCTION_ENTITY]
            ),
        }

        now = dt_util.now()
        ts = now.timestamp()
        consumption_w = status[FIELD_CONSUMPTION_W]
        grid_w = status[FIELD_GRID_FEED_IN_W]
        production_w = status[FIELD_PRODUCTION_W]
        import_w, export_w = split_grid(grid_w)

        if self.current_date is not None and day_changed(self.current_date, now):
            self._roll_over(now)

        metrics = {
            COUNTER_CONSUMPTION: consumption_w,
            COUNTER_GRID_IMPORT: import_w,
            COUNTER_GRID_EXPORT: export_w,
            COUNTER_PRODUCTION: production_w,
        }
        for key, w in metrics.items():
            prev = self.prev_samples.get(key)
            sample = Sample(ts=ts, w=w)
            if prev is not None:
                wh = integrate(prev, sample)
                if wh is not None:
                    self.counters_wh[key] += wh
            self.prev_samples[key] = sample

        if self.current_date is None:
            self.current_date = now.date()
            self.last_reset = now

        return status

    def _roll_over(self, now: datetime) -> None:
        for key in COUNTERS:
            self.last_period_wh[key] = self.counters_wh[key]
            self.counters_wh[key] = 0.0
        self.current_date = now.date()
        self.last_reset = now
        _LOGGER.info(
            "Tageswechsel erkannt: Zaehler zurueckgesetzt, last_period gespeichert"
        )

    def restore_counter(
        self,
        key: str,
        kwh: float,
        last_period_kwh: float,
        last_reset: datetime | None,
        prev_sample: Sample | None,
    ) -> None:
        """Seed für einen Tageszähler nach einem HA-Neustart (RestoreEntity)."""
        self.counters_wh[key] = kwh * 1000.0
        self.last_period_wh[key] = last_period_kwh * 1000.0
        if last_reset is not None:
            self.last_reset = last_reset
            self.current_date = last_reset.date()
        if key not in self.prev_samples and prev_sample is not None:
            self.prev_samples[key] = prev_sample

    @property
    def autarky_today(self) -> float:
        return autarky_degree(
            self.counters_wh[COUNTER_GRID_IMPORT],
            self.counters_wh[COUNTER_CONSUMPTION],
        )

    @property
    def autarky_yesterday(self) -> float:
        return autarky_degree(
            self.last_period_wh[COUNTER_GRID_IMPORT],
            self.last_period_wh[COUNTER_CONSUMPTION],
        )

    @property
    def self_consumption_today(self) -> float:
        return self_consumption_rate(
            self.counters_wh[COUNTER_GRID_EXPORT],
            self.counters_wh[COUNTER_PRODUCTION],
        )

    @property
    def self_consumption_yesterday(self) -> float:
        return self_consumption_rate(
            self.last_period_wh[COUNTER_GRID_EXPORT],
            self.last_period_wh[COUNTER_PRODUCTION],
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SonnenAutarkyCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Initiales Lesen der Quell-Sensoren fehlgeschlagen: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
