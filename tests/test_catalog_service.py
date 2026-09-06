"""Unit Tests for EchoDrive Vehicle Catalog Service and RAG Context."""

import pytest
from backend.app.catalog.models import BodyType, FuelType, VehicleSpec
from backend.app.catalog.catalog_service import CatalogService


@pytest.fixture
def catalog():
    return CatalogService()


def test_catalog_initialization(catalog):
    vehicles = catalog.get_all_vehicles()
    assert len(vehicles) >= 10
    assert any(v.make == "Mercedes-Benz" for v in vehicles)
    assert any(v.make == "BMW" for v in vehicles)
    assert any(v.make == "Mahindra" for v in vehicles)


def test_search_by_make(catalog):
    result = catalog.search(make="Mercedes-Benz")
    assert len(result.vehicles) > 0
    assert all(v.make == "Mercedes-Benz" for v in result.vehicles)


def test_search_by_body_type(catalog):
    result = catalog.search(body_type=BodyType.SUV)
    assert len(result.vehicles) > 0
    assert all(v.body_type == BodyType.SUV for v in result.vehicles)


def test_search_by_budget(catalog):
    # Budget under 35 Lakhs
    result = catalog.search(max_budget_inr=3500000)
    assert len(result.vehicles) > 0
    assert all(v.ex_showroom_price_inr <= 3500000 for v in result.vehicles)


def test_search_from_user_text_mercedes(catalog):
    user_query = "I am looking for a black Mercedes sedan within 80 lakhs"
    matches = catalog.search_from_user_text(user_query, limit=2)
    assert len(matches) > 0
    assert matches[0].make == "Mercedes-Benz"
    assert matches[0].body_type == BodyType.SEDAN


def test_search_from_user_text_crore_budget(catalog):
    user_query = "What options do you have around 1 Crore or 1 Cr?"
    matches = catalog.search_from_user_text(user_query, limit=3)
    assert len(matches) > 0
    # Should include cars like BMW X5, Audi Q7, or Mercedes E-Class/GLC
    assert any("Crore" in v.formatted_price_display or v.ex_showroom_price_inr >= 6000000 for v in matches)


def test_format_rag_context(catalog):
    matches = catalog.search(make="Mercedes-Benz", limit=2).vehicles
    context_str = catalog.format_rag_context(matches)
    assert "### Authoritative Dealership Live Inventory & Pricing" in context_str
    assert "Mercedes-Benz" in context_str
    assert "Ex-Showroom" in context_str
