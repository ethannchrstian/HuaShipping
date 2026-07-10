"""Shared builders for model tests — real names from the sheets."""

import pytest

from voyages.models import Charterer, Jetty, Vessel, Voyage


@pytest.fixture
def vessel(db):
    return Vessel.objects.create(
        name="TB. HUA Navigator 1 & BG. Palm Hero 2401",
        tug_name="TB. HUA Navigator 1",
        barge_name="BG. Palm Hero 2401",
    )


@pytest.fixture
def vessel2(db):
    return Vessel.objects.create(
        name="TB. HUA Navigator 2 & BG. Palm Hero 2402",
        tug_name="TB. HUA Navigator 2",
        barge_name="BG. Palm Hero 2402",
    )


@pytest.fixture
def jetty(db):
    return Jetty.objects.create(name="Jetty PT. Sahabat Mewah Makmur", port="Belitung")


@pytest.fixture
def charterer(db):
    return Charterer.objects.create(code="FPS", name="First Palm Shipping")


@pytest.fixture
def voyage(vessel):
    return Voyage.objects.create(code="V2601", vessel=vessel, contract_no="001/FN-HUAT/I/2026")
