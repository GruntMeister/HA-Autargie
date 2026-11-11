"""Config-Flow-Tests. Benötigt pytest-homeassistant-custom-component."""

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sonnen_autarky.api import SonnenApiError, SonnenAuthError
from custom_components.sonnen_autarky.const import (
    CONF_AUTH_TOKEN,
    CONF_IP_ADDRESS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

VALID_STATUS = {
    "Consumption_W": 500,
    "GridFeedIn_W": -200,
    "Pac_total_W": 300,
    "Production_W": 1500,
    "SerialNumber": "12345678",
}

USER_INPUT = {
    CONF_IP_ADDRESS: "192.168.1.50",
    CONF_AUTH_TOKEN: "geheim-token",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


async def test_user_flow_gueltiger_token(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.sonnen_autarky.config_flow.SonnenApiClient.async_get_status",
        new=AsyncMock(return_value=VALID_STATUS),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_IP_ADDRESS] == "192.168.1.50"
    assert result["data"][CONF_AUTH_TOKEN] == "geheim-token"


async def test_user_flow_falscher_token(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.sonnen_autarky.config_flow.SonnenApiClient.async_get_status",
        new=AsyncMock(side_effect=SonnenAuthError("401")),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_ip_nicht_erreichbar(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.sonnen_autarky.config_flow.SonnenApiClient.async_get_status",
        new=AsyncMock(side_effect=SonnenApiError("timeout")),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant):
    with patch(
        "custom_components.sonnen_autarky.config_flow.SonnenApiClient.async_get_status",
        new=AsyncMock(return_value=VALID_STATUS),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    entry = result["result"]
    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert options_result["type"] == FlowResultType.FORM
    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert options_result["type"] == FlowResultType.CREATE_ENTRY
    assert options_result["data"][CONF_SCAN_INTERVAL] == 60
