"""Konstanten der Sonnen Autarky Integration."""

DOMAIN = "sonnen_autarky"

CONF_IP_ADDRESS = "ip_address"
CONF_AUTH_TOKEN = "auth_token"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300

API_PATH = "/api/v2/status"
API_TIMEOUT = 10

ATTR_LAST_PERIOD = "last_period"
ATTR_LAST_RESET = "last_reset"

FIELD_CONSUMPTION_W = "Consumption_W"
FIELD_GRID_FEED_IN_W = "GridFeedIn_W"
FIELD_PAC_TOTAL_W = "Pac_total_W"
FIELD_PRODUCTION_W = "Production_W"
FIELD_SERIAL_NUMBER = "SerialNumber"

COUNTER_CONSUMPTION = "consumption"
COUNTER_GRID_IMPORT = "grid_import"
COUNTER_GRID_EXPORT = "grid_export"
COUNTER_PRODUCTION = "production"
COUNTERS = (
    COUNTER_CONSUMPTION,
    COUNTER_GRID_IMPORT,
    COUNTER_GRID_EXPORT,
    COUNTER_PRODUCTION,
)
