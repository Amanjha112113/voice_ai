"""FastAPI Endpoints for EchoDrive Automotive Inventory and Catalog."""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from ..catalog.models import VehicleSpec, BodyType, FuelType
from ..catalog.catalog_service import catalog_service

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/vehicles", response_model=List[dict])
async def list_vehicles(
    query: Optional[str] = Query(None, description="Search query keywords"),
    make: Optional[str] = Query(None, description="Filter by make (e.g., Mercedes-Benz, BMW, Mahindra)"),
    body_type: Optional[BodyType] = Query(None, description="Filter by body type"),
    fuel_type: Optional[FuelType] = Query(None, description="Filter by fuel type"),
    max_budget: Optional[int] = Query(None, description="Maximum budget in INR"),
    min_budget: Optional[int] = Query(None, description="Minimum budget in INR"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search and filter available dealership inventory."""
    result = catalog_service.search(
        query=query,
        make=make,
        body_type=body_type,
        fuel_type=fuel_type,
        max_budget_inr=max_budget,
        min_budget_inr=min_budget,
        limit=limit,
    )
    return [
        {
            "make": v.make,
            "model": v.model,
            "variant": v.variant,
            "body_type": v.body_type.value,
            "fuel_type": v.fuel_type.value,
            "transmission": v.transmission,
            "power_bhp": v.power_bhp,
            "torque_nm": v.torque_nm,
            "acceleration_0_100_s": v.acceleration_0_100_s,
            "mileage_kmpl": v.mileage_kmpl,
            "ev_range_km": v.ev_range_km,
            "ex_showroom_price_inr": v.ex_showroom_price_inr,
            "on_road_estimate_inr": v.on_road_estimate_inr,
            "price_display": v.formatted_price_display,
            "in_stock_units": v.in_stock_units,
            "key_features": v.key_features,
            "colors_available": v.colors_available,
        }
        for v in result.vehicles
    ]


@router.get("/summary")
async def get_catalog_summary():
    """Get high-level catalog statistics."""
    all_v = catalog_service.get_all_vehicles()
    makes = list(set(v.make for v in all_v))
    total_stock = sum(v.in_stock_units for v in all_v)
    return {
        "total_models": len(all_v),
        "brands_available": sorted(makes),
        "total_units_in_stock": total_stock,
    }
