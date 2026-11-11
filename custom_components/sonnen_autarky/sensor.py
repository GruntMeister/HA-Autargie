"""Sensor-Platform der Sonnen Autarky Integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SonnenAutarkyCoordinator
from .calc import Sample, live_autarky
from .const import (
    ATTR_LAST_PERIOD,
    ATTR_LAST_RESET,
    COUNTER_CONSUMPTION,
    COUNTER_GRID_EXPORT,
    COUNTER_GRID_IMPORT,
    DOMAIN,
    FIELD_CONSUMPTION_W,
    FIELD_GRID_FEED_IN_W,
)

_LOGGER = logging.getLogger(__name__)


class SonnenAutarkyBase(CoordinatorEntity[SonnenAutarkyCoordinator]):
    """Gemeinsame Basis: Device-Info und has_entity_name."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial_number)},
            name="sonnenBatterie",
            manufacturer="sonnen GmbH",
            serial_number=self.coordinator.serial_number,
        )


class SonnenDailyEnergySensor(SonnenAutarkyBase, RestoreEntity, SensorEntity):
    """Tageszähler (kWh) mit Mitternachts-Reset und Restore nach HA-Neustart."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self, coordinator: SonnenAutarkyCoordinator, counter: str, translation_key: str
    ) -> None:
        super().__init__(coordinator)
        self._counter = counter
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.serial_number}_{counter}"

    @property
    def native_value(self) -> float:
        return round(self.coordinator.counters_wh[self._counter] / 1000.0, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            ATTR_LAST_PERIOD: round(
                self.coordinator.last_period_wh[self._counter] / 1000.0, 3
            )
        }
        if self.coordinator.last_reset is not None:
            attrs[ATTR_LAST_RESET] = self.coordinator.last_reset.isoformat()
        return attrs

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        prev = self.coordinator.prev_samples.get(self._counter)
        return ExtraStoredData(
            {
                "kwh": round(self.coordinator.counters_wh[self._counter] / 1000.0, 6),
                "last_period_kwh": round(
                    self.coordinator.last_period_wh[self._counter] / 1000.0, 6
                ),
                "last_reset": (
                    self.coordinator.last_reset.isoformat()
                    if self.coordinator.last_reset
                    else None
                ),
                "prev_sample_ts": prev.ts if prev else None,
                "prev_sample_w": prev.w if prev else None,
            }
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_extra_data()
        if last is None:
            _LOGGER.warning(
                "Kein Restore-State fuer %s - starte bei 0", self._attr_unique_id
            )
            return
        data = last.as_dict()
        try:
            kwh = float(data["kwh"])
            last_period_kwh = float(data.get("last_period_kwh") or 0.0)
            last_reset_raw = data.get("last_reset")
            last_reset = (
                datetime.fromisoformat(last_reset_raw) if last_reset_raw else None
            )
            prev: Sample | None = None
            if (
                data.get("prev_sample_ts") is not None
                and data.get("prev_sample_w") is not None
            ):
                prev = Sample(
                    ts=float(data["prev_sample_ts"]), w=float(data["prev_sample_w"])
                )
            self.coordinator.restore_counter(
                self._counter, kwh, last_period_kwh, last_reset, prev
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Restore-State fuer %s beschaedigt (%s) - starte bei 0",
                self._attr_unique_id,
                err,
            )


class SonnenPercentageSensor(SonnenAutarkyBase, SensorEntity):
    """Basis für %-Sensoren (measurement)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: SonnenAutarkyCoordinator, translation_key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.serial_number}_{translation_key}"


class SonnenAutarkyTodaySensor(SonnenPercentageSensor):
    """Autarkiegrad heute in % aus den Tageszählern."""

    def __init__(self, coordinator: SonnenAutarkyCoordinator) -> None:
        super().__init__(coordinator, "autarkiegrad_heute")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.autarky_today, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_LAST_PERIOD: round(self.coordinator.autarky_yesterday, 1),
            "netzbezug_heute_kwh": round(
                self.coordinator.counters_wh[COUNTER_GRID_IMPORT] / 1000.0, 3
            ),
            "hausverbrauch_heute_kwh": round(
                self.coordinator.counters_wh[COUNTER_CONSUMPTION] / 1000.0, 3
            ),
        }


class SonnenLiveAutarkySensor(SonnenPercentageSensor):
    """Autarkiegrad aktuell in % aus den Momentanleistungen."""

    def __init__(self, coordinator: SonnenAutarkyCoordinator) -> None:
        super().__init__(coordinator, "autarkiegrad_aktuell")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if not data:
            return None
        return round(
            live_autarky(
                float(data[FIELD_GRID_FEED_IN_W]),
                float(data[FIELD_CONSUMPTION_W]),
            ),
            1,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "grid_feed_in_w": round(float(data[FIELD_GRID_FEED_IN_W]), 1),
            "hausverbrauch_w": round(float(data[FIELD_CONSUMPTION_W]), 1),
        }


class SonnenSelfConsumptionSensor(SonnenPercentageSensor):
    """Eigenverbrauchsquote heute in % aus Produktion und Einspeisung."""

    def __init__(self, coordinator: SonnenAutarkyCoordinator) -> None:
        super().__init__(coordinator, "eigenverbrauchsquote_heute")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.self_consumption_today, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_LAST_PERIOD: round(self.coordinator.self_consumption_yesterday, 1)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SonnenAutarkyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SonnenDailyEnergySensor(
                coordinator, COUNTER_CONSUMPTION, "hausverbrauch_heute"
            ),
            SonnenDailyEnergySensor(
                coordinator, COUNTER_GRID_IMPORT, "netzbezug_heute"
            ),
            SonnenDailyEnergySensor(
                coordinator, COUNTER_GRID_EXPORT, "netzeinspeisung_heute"
            ),
            SonnenAutarkyTodaySensor(coordinator),
            SonnenLiveAutarkySensor(coordinator),
            SonnenSelfConsumptionSensor(coordinator),
        ]
    )
