"""Unit-Tests für die reinen Rechenfunktionen in calc.py (ohne HA)."""

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "sonnen_autarky")
)

from calc import (
    MAX_GAP_SECONDS,
    Sample,
    autarky_degree,
    day_changed,
    integrate,
    live_autarky,
    self_consumption_rate,
    split_grid,
)


class TestIntegrate:
    def test_konstante_last_ueber_12x_300s(self):
        total = 0.0
        ts = 0.0
        prev = Sample(ts=ts, w=1000.0)
        for _ in range(12):
            ts += 300.0
            sample = Sample(ts=ts, w=1000.0)
            wh = integrate(prev, sample)
            assert wh is not None
            total += wh
            prev = sample
        assert total == pytest.approx(1000.0)

    def test_lastspitze_trapez(self):
        prev = Sample(ts=0.0, w=0.0)
        sample = Sample(ts=300.0, w=2000.0)
        assert integrate(prev, sample) == pytest.approx(2000.0 / 2 * 300.0 / 3600.0)

    def test_gleiches_ergebnis_30s_schritte(self):
        total = 0.0
        ts = 0.0
        prev = Sample(ts=ts, w=500.0)
        for _ in range(120):
            ts += 30.0
            sample = Sample(ts=ts, w=500.0)
            wh = integrate(prev, sample)
            assert wh is not None
            total += wh
            prev = sample
        assert total == pytest.approx(500.0)

    def test_dt_gleich_null_gibt_none(self):
        prev = Sample(ts=100.0, w=100.0)
        assert integrate(prev, Sample(ts=100.0, w=100.0)) is None

    def test_rueckwaerts_gibt_none(self):
        prev = Sample(ts=200.0, w=100.0)
        assert integrate(prev, Sample(ts=100.0, w=100.0)) is None

    def test_luecke_ueber_max_gap_gibt_none(self):
        prev = Sample(ts=0.0, w=1000.0)
        sample = Sample(ts=MAX_GAP_SECONDS + 1, w=1000.0)
        assert integrate(prev, sample) is None

    def test_genau_max_gap_wird_integriert(self):
        prev = Sample(ts=0.0, w=1000.0)
        sample = Sample(ts=MAX_GAP_SECONDS, w=1000.0)
        assert integrate(prev, sample) == pytest.approx(MAX_GAP_SECONDS / 3.6)


class TestSplitGrid:
    def test_negativ_ist_netzbezug(self):
        assert split_grid(-500.0) == (500.0, 0.0)

    def test_positiv_ist_einspeisung(self):
        assert split_grid(300.0) == (0.0, 300.0)

    def test_null(self):
        assert split_grid(0.0) == (0.0, 0.0)


class TestAutarkyDegree:
    def test_vollstaendig_autark(self):
        assert autarky_degree(0.0, 5000.0) == pytest.approx(100.0)

    def test_halb_autark(self):
        assert autarky_degree(2500.0, 5000.0) == pytest.approx(50.0)

    def test_kein_verbrauch_gibt_null(self):
        assert autarky_degree(100.0, 0.0) == 0.0
        assert autarky_degree(0.0, 0.0) == 0.0

    def test_bezug_ueber_verbrauch_wird_geklemmt(self):
        assert autarky_degree(10000.0, 5000.0) == 0.0

    def test_wird_auf_100_geklemmt(self):
        assert autarky_degree(-1.0, 5000.0) == 100.0


class TestLiveAutarky:
    def test_netzbezug(self):
        assert live_autarky(-1000.0, 4000.0) == pytest.approx(75.0)

    def test_einspeisung_ist_100_prozent(self):
        assert live_autarky(500.0, 4000.0) == pytest.approx(100.0)

    def test_kein_verbrauch_gibt_null(self):
        assert live_autarky(-100.0, 0.0) == 0.0


class TestSelfConsumptionRate:
    def test_keine_einspeisung(self):
        assert self_consumption_rate(0.0, 8000.0) == pytest.approx(100.0)

    def test_haelfte_eingespeist(self):
        assert self_consumption_rate(4000.0, 8000.0) == pytest.approx(50.0)

    def test_keine_produktion_gibt_null(self):
        assert self_consumption_rate(100.0, 0.0) == 0.0

    def test_wird_geklemmt(self):
        assert self_consumption_rate(10000.0, 5000.0) == 0.0


class TestDayChanged:
    def test_gleicher_tag(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)
        assert day_changed(date(2025, 6, 15), now) is False

    def test_datumswechsel(self):
        now = datetime(2025, 6, 16, 0, 5, tzinfo=UTC)
        assert day_changed(date(2025, 6, 15), now) is True

    def test_sommerzeit_umstellung_bleibt_stabil(self):
        prev = date(2025, 3, 29)
        now = datetime(2025, 3, 30, 12, 0, tzinfo=UTC)
        assert day_changed(prev, now) is True
        same_day = datetime(2025, 3, 30, 1, 0, tzinfo=UTC)
        assert day_changed(date(2025, 3, 30), same_day) is False


class TestTagesakkumulation:
    """Simulierter Tagesablauf: konstante Werte, Reset um Mitternacht, Lücke."""

    def _run_day(self, w, seconds=86400, step=30):
        counters = 0.0
        ts = 0.0
        prev = Sample(ts=ts, w=w)
        end = ts + seconds
        while ts < end:
            ts = min(ts + step, end)
            sample = Sample(ts=ts, w=w)
            wh = integrate(prev, sample)
            if wh is not None:
                counters += wh
            prev = sample
        return counters

    def test_konstanter_24h_tag(self):
        assert self._run_day(1000.0) == pytest.approx(24000.0)

    def test_luecke_schneidet_ab(self):
        prev = Sample(ts=0.0, w=1000.0)
        sample = Sample(ts=300.0, w=1000.0)
        assert integrate(prev, sample) is not None
        gap = Sample(ts=300.0 + MAX_GAP_SECONDS + 60, w=1000.0)
        assert integrate(sample, gap) is None
