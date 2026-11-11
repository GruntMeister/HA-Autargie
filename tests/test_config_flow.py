"""Config-Flow-Tests. Benötigt pytest-homeassistant-custom-component."""

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sonnen_autarky.const import (
    CONF_CONSUMPTION_ENTITY,
    CONF_GRID_FEED_IN_ENTITY,
    CONF_PRODUCTION_ENTITY,
    CONF_SOURCE_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

ENTITY_CONSUMPTION = "sensor.sonnen_hausverbrauch_w"
ENTITY_GRID = "sensor.sonnen_grid_feed_in_w"
ENTITY_PRODUCTION = "sensor.sonnen_pv_produktion_w"

USER_INPUT = {
    CONF_CONSUMPTION_ENTITY: ENTITY_CONSUMPTION,
    CONF_GRID_FEED_IN_ENTITY: ENTITY_GRID,
    CONF_PRODUCTION_ENTITY: ENTITY_PRODUCTION,
    CONF_SOURCE_UNIT: "W",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}


def _set_source_states(hass: HomeAssistant) -> None:
    hass.states.async_set(ENTITY_CONSUMPTION, "500")
    hass.states.async_set(ENTITY_GRID, "-200")
    hass.states.async_set(ENTITY_PRODUCTION, "1500")


async def test_user_flow_ok(hass: HomeAssistant):
    _set_source_states(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CONSUMPTION_ENTITY] == ENTITY_CONSUMPTION
    assert result["data"][CONF_GRID_FEED_IN_ENTITY] == ENTITY_GRID
    assert result["data"][CONF_PRODUCTION_ENTITY] == ENTITY_PRODUCTION
    assert result["data"][CONF_SOURCE_UNIT] == "W"


async def test_user_flow_einheit_kilowatt(hass: HomeAssistant):
    _set_source_states(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_SOURCE_UNIT: "kW"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOURCE_UNIT] == "kW"


async def test_user_flow_sensor_unavailable(hass: HomeAssistant):
    hass.states.async_set(ENTITY_CONSUMPTION, "unavailable")
    hass.states.async_set(ENTITY_GRID, "-200")
    hass.states.async_set(ENTITY_PRODUCTION, "1500")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_CONSUMPTION_ENTITY: "invalid_entity"}


async def test_user_flow_sensors_missing(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {
        CONF_CONSUMPTION_ENTITY: "invalid_entity",
        CONF_GRID_FEED_IN_ENTITY: "invalid_entity",
        CONF_PRODUCTION_ENTITY: "invalid_entity",
    }


async def test_options_flow(hass: HomeAssistant):
    _set_source_states(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    entry = result["result"]

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    assert options_result["type"] == FlowResultType.FORM
    options_result = await hass.config_entries.options.async_configure(
        options_result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert options_result["type"] == FlowResultType.CREATE_ENTRY
    assert options_result["data"][CONF_SCAN_INTERVAL] == 60
