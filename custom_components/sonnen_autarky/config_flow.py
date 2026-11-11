"""Config Flow (UI) und Options Flow für Sonnen Autarky."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SCAN_INTERVAL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .calc import SOURCE_UNITS, UNIT_WATT
from .const import (
    CONF_CONSUMPTION_ENTITY,
    CONF_GRID_FEED_IN_ENTITY,
    CONF_PRODUCTION_ENTITY,
    CONF_SOURCE_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SOURCE_ENTITIES,
)

_SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONSUMPTION_ENTITY): _SENSOR_SELECTOR,
        vol.Required(CONF_GRID_FEED_IN_ENTITY): _SENSOR_SELECTOR,
        vol.Required(CONF_PRODUCTION_ENTITY): _SENSOR_SELECTOR,
        vol.Required(CONF_SOURCE_UNIT, default=UNIT_WATT): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(SOURCE_UNITS), translation_key=CONF_SOURCE_UNIT
            )
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
    }
)


def _options_schema(current: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            )
        }
    )


def _entity_numeric(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False
    try:
        float(state.state)
    except ValueError:
        return False
    return True


class SonnenAutarkyConfigFlow(ConfigFlow, domain=DOMAIN):
    """UI-Konfiguration: Auswahl der Quell-Sensoren der sonnenBatterie-Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            for key in SOURCE_ENTITIES:
                if not _entity_numeric(self.hass, user_input[key]):
                    errors[key] = "invalid_entity"
            if not errors:
                registry = er.async_get(self.hass)
                reg_entry = registry.async_get(user_input[CONF_CONSUMPTION_ENTITY])
                if reg_entry and reg_entry.device_id:
                    unique_id = reg_entry.device_id
                else:
                    digest = hashlib.sha1(
                        "|".join(
                            sorted(user_input[k] for k in SOURCE_ENTITIES)
                        ).encode()
                    ).hexdigest()[:16]
                    unique_id = digest
                await self.async_set_unique_id(str(unique_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sonnen Autarky",
                    data={
                        **{key: user_input[key] for key in SOURCE_ENTITIES},
                        CONF_SOURCE_UNIT: user_input[CONF_SOURCE_UNIT],
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    USER_SCHEMA, user_input
                ),
                errors=errors,
            )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SonnenAutarkyOptionsFlow:
        return SonnenAutarkyOptionsFlow()


class SonnenAutarkyOptionsFlow(OptionsFlow):
    """Optionen: nur das Abrufintervall."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = int(
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(current)
        )
