"""Config Flow (UI) und Options Flow für Sonnen Autarky."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SonnenApiClient, SonnenApiError, SonnenAuthError
from .const import (
    CONF_AUTH_TOKEN,
    CONF_IP_ADDRESS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FIELD_SERIAL_NUMBER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_AUTH_TOKEN): str,
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


class SonnenAutarkyConfigFlow(ConfigFlow, domain=DOMAIN):
    """UI-Konfiguration: IP, Auth-Token, Intervall - mit Live-Validierung."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = (
                user_input[CONF_IP_ADDRESS]
                .strip()
                .removeprefix("http://")
                .removeprefix("https://")
                .removesuffix("/")
            )
            token = user_input[CONF_AUTH_TOKEN].strip()
            client = SonnenApiClient(async_get_clientsession(self.hass), host, token)
            try:
                status = await client.async_get_status()
            except SonnenAuthError:
                errors["base"] = "invalid_auth"
            except SonnenApiError:
                errors["base"] = "cannot_connect"
            else:
                serial = str(status.get(FIELD_SERIAL_NUMBER) or host)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"sonnenBatterie ({host})",
                    data={
                        CONF_IP_ADDRESS: host,
                        CONF_AUTH_TOKEN: token,
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
