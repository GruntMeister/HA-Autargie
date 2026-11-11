# Sonnen Autarky

Custom Integration für Home Assistant, die aus den **Watt-Sensoren einer bestehenden
sonnenBatterie-Integration** die **Tages-Autarkie** als fertige Sensoren berechnet –
ohne Integral-, Utility-Meter- oder Template-Helfer und ohne erneutes API-Polling.

[![Open your Home Assistant instance and add this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=GruntMeister&repository=HA-Autargie&category=integration)

## Voraussetzung

Eine bereits eingerichtete sonnenBatterie-Integration, die folgende Sensoren als
numerische Watt-Werte bereitstellt (z. B. weltmeyer/ha_sonnenbatterie):

- Hausverbrauch (`Consumption_W`)
- GridFeedIn (`GridFeedIn_W`) – negativ = Netzbezug, positiv = Einspeisung
- PV-Produktion (`Production_W`)

## Funktionen

- Liest die Quell-Sensoren im konfigurierbaren Intervall (Standard 30 s)
- Zeitgewichtete Akkumulation von W → kWh über den Tag (Trapez-Verfahren)
- Mitternachts-Reset über Datumswechsel (sommerzeit-sicher, kein fixer Timer)
- Restore der Tageszähler nach HA-Neustart (`RestoreEntity`)
- Vortageswerte je Zähler als Attribut `last_period`
- Sind Quell-Sensoren `unavailable`, gehen die eigenen Sensoren auf `unavailable`
  und die Zähler frieren ein; Lücken > 5 min werden nicht extrapoliert

## Sensoren

| Sensor | Einheit | Berechnung |
|---|---|---|
| Autarkiegrad heute | % | `(1 − Netzbezug/Verbrauch) · 100` |
| Autarkiegrad aktuell | % | Live-Wert aus Momentanleistung |
| Hausverbrauch heute | kWh | Integral aus dem Verbrauchssensor |
| Netzbezug heute | kWh | Integral aus `max(0, −GridFeedIn)` |
| Netzeinspeisung heute | kWh | Integral aus `max(0, GridFeedIn)` |
| Eigenverbrauchsquote heute | % | `(1 − Einspeisung/Produktion) · 100` |

## Installation

1. Repo in HACS als benutzerdefiniertes Repository hinzufügen (Kategorie: Integration)
2. „Sonnen Autarky" installieren und HA neu starten
3. In HA unter **Einstellungen > Geräte & Dienste > Hinzufügen** „Sonnen Autarky" wählen
4. Die drei Quell-Sensoren der sonnenBatterie-Integration auswählen und optional das Abrufintervall anpassen

## Tests

```bash
pip install pytest pytest-homeassistant-custom-component
pytest tests/
```

Die Rechenlogik (`calc.py`) ist als reine Funktionen ohne HA-Abhängigkeit umgesetzt
und wird in `tests/test_calc.py` ohne Home Assistant getestet.

## Bekannte Einschränkungen

- HA-Downtime innerhalb eines Tages fehlt im Tageszähler (kein Zurückrechnen aus der History)
- Die Quell-Sensoren müssen numerische Watt-Werte liefern; Einheiten-Konvertierung
  (z. B. kW statt W) übernimmt die bestehende sonnenBatterie-Integration
