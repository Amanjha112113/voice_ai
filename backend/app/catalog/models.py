"""Catalog Data Models for EchoDrive Automotive Dealership Inventory."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class FuelType(str, Enum):
    PETROL = "Petrol"
    DIESEL = "Diesel"
    ELECTRIC = "Electric"
    HYBRID = "Strong Hybrid"
    MILD_HYBRID = "Mild Hybrid"


class BodyType(str, Enum):
    SEDAN = "Sedan"
    SUV = "SUV"
    COUPE = "Coupe"
    HATCHBACK = "Hatchback"
    CONVERTIBLE = "Convertible"


@dataclass
class VehicleSpec:
    """Detailed specifications of a vehicle model."""
    make: str  # e.g., Mercedes-Benz, BMW, Mahindra
    model: str  # e.g., C-Class, 3 Series LCI, XUV700
    variant: str  # e.g., C 220d AMG Line, 330Li M Sport
    body_type: BodyType
    fuel_type: FuelType
    transmission: str  # e.g., 9-Speed G-Tronic, 8-Speed Steptronic
    engine_displacement: str  # e.g., 1993 cc, Dual Motor EV
    power_bhp: int  # e.g., 200 bhp
    torque_nm: int  # e.g., 440 Nm
    acceleration_0_100_s: float  # e.g., 7.3 s
    mileage_kmpl: Optional[float] = None
    ev_range_km: Optional[int] = None
    seating_capacity: int = 5
    key_features: List[str] = field(default_factory=list)
    colors_available: List[str] = field(default_factory=list)
    ex_showroom_price_inr: int = 0  # In INR Rupees
    on_road_estimate_inr: int = 0  # In INR Rupees
    in_stock_units: int = 0
    test_drive_available: bool = True

    @property
    def price_lakhs(self) -> float:
        return round(self.ex_showroom_price_inr / 100_000, 2)

    @property
    def price_crores(self) -> float:
        return round(self.ex_showroom_price_inr / 10_000_000, 2)

    @property
    def formatted_price_display(self) -> str:
        if self.ex_showroom_price_inr >= 10_000_000:
            return f"₹{self.price_crores} Crore (Ex-Showroom) / ₹{round(self.on_road_estimate_inr / 10_000_000, 2)} Cr (On-Road)"
        else:
            return f"₹{self.price_lakhs} Lakh (Ex-Showroom) / ₹{round(self.on_road_estimate_inr / 100_000, 2)} Lakh (On-Road)"


@dataclass
class CatalogSearchResult:
    """Result of catalog search query."""
    query: str
    vehicles: List[VehicleSpec] = field(default_factory=list)
    total_matched: int = 0
