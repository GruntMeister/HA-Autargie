# Sonnen Autarky

Custom Integration für Home Assistant, die aus der **lokalen sonnenBatterie-API v2**
(`http://<IP>/api/v2/status`) die **Tages-Autarkie** als fertige Sensoren liefert –
ohne Integral-, Utility-Meter- oder Template-Helfer.

[![Open your Home Assistant instance and add this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=GruntMeister&repository=HA-Autargie&category=integration)

## Funktionen

- Polling der lokalen API v2 mit `Auth-Token`-Header (Standard 30 s, konfigurierbar)
- Zeitgewichtete Akkumulation von W → kWh über den Tag (Trapez-Verfahren)
- Mitternachts-Reset über Datumswechsel (sommerzeit-sicher, kein fixer Timer)
- Restore der Tageszähler nach HA-Neustart (`RestoreEntity`)
- Vortageswerte je Zähler als Attribut `last_period`
- Bei API-Ausfall: Sensoren `unavailable`, Zähler frieren ein; Ausfallzeiten
  werden über eine Lücken-Grenze (5 min) nicht extrapoliert

## Sensoren

| Sensor | Einheit | Berechnung |
|---|---|---|
| Autarkiegrad heute | % | `(1 − Netzbezug/Verbrauch) · 100` |
| Autarkiegrad aktuell | % | Live-Wert aus Momentanleistung |
| Hausverbrauch heute | kWh | Integral aus `Consumption_W` |
| Netzbezug heute | kWh | Integral aus `max(0, −GridFeedIn_W)` |
| Netzeinspeisung heute | kWh | Integral aus `max(0, GridFeedIn_W)` |
| Eigenverbrauchsquote heute | % | `(1 − Einspeisung/Produktion) · 100` |

Vorzeichenkonvention der API: `GridFeedIn_W` negativ = Netzbezug, positiv = Einspeisung.

## Installation

1. Repo in HACS als benutzerdefiniertes Repository hinzufügen (Kategorie: Integration)
2. „Sonnen Autarky" installieren und HA neu starten
3. In HA unter **Einstellungen > Geräte & Dienste > Hinzufügen** „Sonnen Autarky" wählen
4. IP-Adresse der Batterie, Auth-Token (lokales Webinterface > Einstellungen > API) und optional das Abrufintervall eingeben

## Tests

```bash
pip install pytest pytest-homeassistant-custom-component
pytest tests/
```

Die Rechenlogik (`calc.py`) ist als reine Funktionen ohne HA-Abhängigkeit umgesetzt
und wird in `tests/test_calc.py` ohne Home Assistant getestet.

## Bekannte Einschränkungen

- HA-Downtime innerhalb eines Tages fehlt im Tageszähler (kein Zurückrechnen aus der History)
- Der Auth-Token liegt im Config-Entry (HA-Speicher); er wird nie geloggt
