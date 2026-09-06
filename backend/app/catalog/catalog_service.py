"""Automotive Catalog Service for EchoDrive.

Provides fast, in-memory authoritative vehicle catalog search, pricing lookup,
and RAG context formatting for LLM prompt augmentation.
"""

from typing import List, Optional, Dict, Any
import re
import logging
from .models import VehicleSpec, FuelType, BodyType, CatalogSearchResult

logger = logging.getLogger(__name__)

# Authoritative Dealership Inventory Dataset
INVENTORY: List[VehicleSpec] = [
    # Mercedes-Benz
    VehicleSpec(
        make="Mercedes-Benz",
        model="C-Class",
        variant="C 220d AMG Line",
        body_type=BodyType.SEDAN,
        fuel_type=FuelType.DIESEL,
        transmission="9G-TRONIC Automatic",
        engine_displacement="1993 cc 4-Cylinder",
        power_bhp=200,
        torque_nm=440,
        acceleration_0_100_s=7.3,
        mileage_kmpl=18.5,
        seating_capacity=5,
        key_features=[
            "11.9-inch Portrait MBUX Display",
            "Burmester 3D Surround Sound",
            "Panoramic Sliding Sunroof",
            "Active Brake Assist & ADAS",
            "64-Color Ambient Lighting",
            "Wireless Apple CarPlay & Android Auto"
        ],
        colors_available=["Obsidian Black", "Polar White", "Selenite Grey", "Mojave Silver"],
        ex_showroom_price_inr=6185000,  # 61.85 Lakhs
        on_road_estimate_inr=7250000,   # ~72.5 Lakhs
        in_stock_units=4,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="Mercedes-Benz",
        model="E-Class",
        variant="E 200 Exclusive LWB",
        body_type=BodyType.SEDAN,
        fuel_type=FuelType.PETROL,
        transmission="9G-TRONIC Automatic",
        engine_displacement="1991 cc Turbocharged",
        power_bhp=204,
        torque_nm=320,
        acceleration_0_100_s=7.6,
        mileage_kmpl=15.0,
        seating_capacity=5,
        key_features=[
            "Superscreen MBUX with Passenger Display",
            "Rear Chauffeur Reclining Package",
            "Air Body Control Air Suspension",
            "Soft-Close Doors",
            "Burmester 4D Audio with Dolby Atmos"
        ],
        colors_available=["Obsidian Black", "High-Tech Silver", "Nautical Blue"],
        ex_showroom_price_inr=7850000,  # 78.5 Lakhs
        on_road_estimate_inr=9200000,   # ~92 Lakhs
        in_stock_units=3,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="Mercedes-Benz",
        model="GLC",
        variant="GLC 300 4MATIC",
        body_type=BodyType.SUV,
        fuel_type=FuelType.PETROL,
        transmission="9G-TRONIC 4MATIC AWD",
        engine_displacement="1999 cc Mild-Hybrid",
        power_bhp=258,
        torque_nm=400,
        acceleration_0_100_s=6.2,
        mileage_kmpl=14.7,
        seating_capacity=5,
        key_features=[
            "Transparent Bonnet Off-Road View",
            "4MATIC All-Wheel Drive",
            "Head-Up Display",
            "Airmatic Air Suspension",
            "Panoramic Sunroof"
        ],
        colors_available=["Obsidian Black", "Polar White", "Manufaktur Patagonia Red"],
        ex_showroom_price_inr=7590000,  # 75.9 Lakhs
        on_road_estimate_inr=8900000,   # ~89 Lakhs
        in_stock_units=5,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="Mercedes-Benz",
        model="S-Class",
        variant="S 350d 4MATIC",
        body_type=BodyType.SEDAN,
        fuel_type=FuelType.DIESEL,
        transmission="9G-TRONIC 4MATIC",
        engine_displacement="2925 cc In-line 6",
        power_bhp=286,
        torque_nm=600,
        acceleration_0_100_s=6.4,
        mileage_kmpl=12.8,
        seating_capacity=5,
        key_features=[
            "Rear Axle Steering (4.5 degrees)",
            "Executive Rear Seats with Massage & Calf Rest",
            "3D Digital Instrument Cluster",
            "Burmester High-End 4D Audio",
            "Active Multibeam Digital Lights"
        ],
        colors_available=["Onyx Black", "Diamond White Bright", "Emerald Green"],
        ex_showroom_price_inr=17700000,  # 1.77 Crore
        on_road_estimate_inr=21000000,   # ~2.10 Crore
        in_stock_units=2,
        test_drive_available=True,
    ),

    # BMW
    VehicleSpec(
        make="BMW",
        model="3 Series Gran Limousine",
        variant="330Li M Sport",
        body_type=BodyType.SEDAN,
        fuel_type=FuelType.PETROL,
        transmission="8-Speed Steptronic Sport",
        engine_displacement="1998 cc TwinPower Turbo",
        power_bhp=258,
        torque_nm=400,
        acceleration_0_100_s=6.2,
        mileage_kmpl=15.3,
        seating_capacity=5,
        key_features=[
            "BMW Curved Display (14.9-inch + 12.3-inch)",
            "Extended Wheelbase for Premium Rear Legroom",
            "Harman Kardon 16-Speaker Surround Sound",
            "Wireless Charging & Parking Assistant Plus",
            "Panoramic Glass Sunroof"
        ],
        colors_available=["Carbon Black", "Mineral White", "Portimao Blue", "Skyscraper Grey"],
        ex_showroom_price_inr=6060000,  # 60.6 Lakhs
        on_road_estimate_inr=7100000,   # ~71 Lakhs
        in_stock_units=4,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="BMW",
        model="X5",
        variant="X5 xDrive40i M Sport",
        body_type=BodyType.SUV,
        fuel_type=FuelType.PETROL,
        transmission="8-Speed Steptronic with xDrive",
        engine_displacement="2998 cc In-line 6 Turbo",
        power_bhp=381,
        torque_nm=520,
        acceleration_0_100_s=5.4,
        mileage_kmpl=12.0,
        seating_capacity=5,
        key_features=[
            "Adaptive 2-Axle Air Suspension",
            "BMW Live Cockpit Professional with HUD",
            "Sky Lounge Panoramic Glass Roof",
            "21-inch M Light Alloy Wheels",
            "Soft Close Doors & Acoustic Glass"
        ],
        colors_available=["Black Sapphire", "Brooklyn Grey", "Mineral White"],
        ex_showroom_price_inr=9700000,  # 97 Lakhs
        on_road_estimate_inr=11400000,  # ~1.14 Crore
        in_stock_units=3,
        test_drive_available=True,
    ),

    # Audi
    VehicleSpec(
        make="Audi",
        model="A6",
        variant="A6 45 TFSI Technology",
        body_type=BodyType.SEDAN,
        fuel_type=FuelType.PETROL,
        transmission="7-Speed S-Tronic Dual Clutch",
        engine_displacement="1984 cc TFSI Turbo",
        power_bhp=245,
        torque_nm=370,
        acceleration_0_100_s=6.8,
        mileage_kmpl=14.1,
        seating_capacity=5,
        key_features=[
            "MMI Dual Touchscreens with Audi Virtual Cockpit",
            "Bang & Olufsen Premium 3D Sound System",
            "Matrix LED Headlights with Dynamic Indicators",
            "Four-Zone Climate Control",
            "Panoramic Glass Sunroof"
        ],
        colors_available=["Mythos Black", "Glacier White", "Firmament Blue", "Ibis White"],
        ex_showroom_price_inr=6776000,  # 67.76 Lakhs
        on_road_estimate_inr=7890000,   # ~78.9 Lakhs
        in_stock_units=3,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="Audi",
        model="Q7",
        variant="Q7 55 TFSI Quattro Technology",
        body_type=BodyType.SUV,
        fuel_type=FuelType.PETROL,
        transmission="8-Speed Tiptronic Quattro AWD",
        engine_displacement="2995 cc V6 Turbo Mild-Hybrid",
        power_bhp=340,
        torque_nm=500,
        acceleration_0_100_s=5.9,
        mileage_kmpl=11.2,
        seating_capacity=7,
        key_features=[
            "7-Seater Configuration with Electric 3rd Row",
            "Quattro All-Wheel Drive with Adaptive Air Suspension",
            "Park Assist Plus with 360-degree Cameras",
            "Bang & Olufsen 3D Sound System",
            "Lane Departure Warning & Audi Pre Sense"
        ],
        colors_available=["Navarra Blue", "Mythos Black", "Samurai Grey"],
        ex_showroom_price_inr=9445000,  # 94.45 Lakhs
        on_road_estimate_inr=11100000,  # ~1.11 Crore
        in_stock_units=2,
        test_drive_available=True,
    ),

    # Mahindra
    VehicleSpec(
        make="Mahindra",
        model="XUV700",
        variant="AX7 Luxury Pack Diesel AT AWD",
        body_type=BodyType.SUV,
        fuel_type=FuelType.DIESEL,
        transmission="6-Speed Torque Converter AWD",
        engine_displacement="2198 cc mHawk Turbo Diesel",
        power_bhp=185,
        torque_nm=450,
        acceleration_0_100_s=9.3,
        mileage_kmpl=16.5,
        seating_capacity=7,
        key_features=[
            "ADAS Level 2 (Adaptive Cruise, Lane Keep, AEB)",
            "Dual 10.25-inch High-Res Superscreen Display",
            "Sony 12-Speaker 3D Audio with Subwoofer",
            "Skyroof Panoramic Sunroof",
            "Flush Smart Door Handles & 360-Degree Camera"
        ],
        colors_available=["Midnight Black", "Electric Blue", "Everest White", "Dazzling Silver"],
        ex_showroom_price_inr=2699000,  # 26.99 Lakhs
        on_road_estimate_inr=3250000,   # ~32.5 Lakhs
        in_stock_units=8,
        test_drive_available=True,
    ),
    VehicleSpec(
        make="Mahindra",
        model="Scorpio-N",
        variant="Z8L 4x4 Diesel AT",
        body_type=BodyType.SUV,
        fuel_type=FuelType.DIESEL,
        transmission="6-Speed Automatic 4XPLOR 4WD",
        engine_displacement="2198 cc mHawk Turbo Diesel",
        power_bhp=175,
        torque_nm=400,
        acceleration_0_100_s=10.2,
        mileage_kmpl=15.0,
        seating_capacity=7,
        key_features=[
            "4XPLOR Intelligent Terrain Management (Snow, Mud, Sand)",
            "Sony 12-Speaker Immersive Audio",
            "Electric Sunroof & Dual Zone Climate Control",
            "Rich Coffee Black Leatherette Interiors",
            "Front & Rear Camera with Parking Assist"
        ],
        colors_available=["Napoli Black", "Deep Forest Green", "Grand Canyon", "Dazzling Silver"],
        ex_showroom_price_inr=2454000,  # 24.54 Lakhs
        on_road_estimate_inr=2950000,   # ~29.5 Lakhs
        in_stock_units=6,
        test_drive_available=True,
    ),

    # Tata Motors
    VehicleSpec(
        make="Tata",
        model="Safari",
        variant="Accomplished Plus 6S Dark Edition AT",
        body_type=BodyType.SUV,
        fuel_type=FuelType.DIESEL,
        transmission="6-Speed Automatic",
        engine_displacement="1956 cc Kryotec Turbo Diesel",
        power_bhp=170,
        torque_nm=350,
        acceleration_0_100_s=10.5,
        mileage_kmpl=16.3,
        seating_capacity=6,
        key_features=[
            "Ventilated 1st and 2nd Row Captain Seats",
            "12.3-inch Cinematic Harman Touchscreen",
            "JBL 10-Speaker Audio with Subwoofer",
            "ADAS Level 2 with 11 Autonomous Features",
            "Voice-Assisted Panoramic Sunroof with Mood Lighting"
        ],
        colors_available=["Oberon Black (Dark Edition)", "Stardust Ash", "Cosmic Gold"],
        ex_showroom_price_inr=2734000,  # 27.34 Lakhs
        on_road_estimate_inr=3280000,   # ~32.8 Lakhs
        in_stock_units=5,
        test_drive_available=True,
    ),

    # Hyundai
    VehicleSpec(
        make="Hyundai",
        model="Ioniq 5",
        variant="Long Range RWD EV",
        body_type=BodyType.SUV,
        fuel_type=FuelType.ELECTRIC,
        transmission="Single Speed Automatic",
        engine_displacement="72.6 kWh High-Density Battery",
        power_bhp=217,
        torque_nm=350,
        acceleration_0_100_s=7.6,
        ev_range_km=631,
        seating_capacity=5,
        key_features=[
            "800V Ultra-Fast Charging (10% to 80% in 18 mins)",
            "Vehicle-to-Load (V2L) Power Outlet",
            "Relaxation Comfort Seats with Ottoman Leg Rest",
            "SmartSense Level 2 ADAS with 21 Features",
            "Bose 8-Speaker Premium Sound System"
        ],
        colors_available=["Midnight Black Pearl", "Gravity Gold Matte", "Optic White"],
        ex_showroom_price_inr=4605000,  # 46.05 Lakhs
        on_road_estimate_inr=4950000,   # ~49.5 Lakhs (EV low tax)
        in_stock_units=3,
        test_drive_available=True,
    ),
]


class CatalogService:
    """Provides fast in-memory vehicle catalog retrieval and context injection."""

    def __init__(self, inventory: Optional[List[VehicleSpec]] = None):
        self._inventory: List[VehicleSpec] = inventory or INVENTORY

    def get_all_vehicles(self) -> List[VehicleSpec]:
        """Return all catalog vehicles."""
        return list(self._inventory)

    def search(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        body_type: Optional[BodyType] = None,
        fuel_type: Optional[FuelType] = None,
        max_budget_inr: Optional[int] = None,
        min_budget_inr: Optional[int] = None,
        limit: int = 5,
    ) -> CatalogSearchResult:
        """Search vehicles by query terms, budget range, brand, and vehicle specifications."""
        results: List[VehicleSpec] = []
        clean_q = (query or "").lower().strip()

        for spec in self._inventory:
            # Filter by Make
            if make and make.lower() not in spec.make.lower():
                continue

            # Filter by Body Type
            if body_type and spec.body_type != body_type:
                continue

            # Filter by Fuel Type
            if fuel_type and spec.fuel_type != fuel_type:
                continue

            # Filter by Budget (check against ex_showroom and on_road)
            if max_budget_inr and spec.ex_showroom_price_inr > max_budget_inr:
                continue
            if min_budget_inr and spec.ex_showroom_price_inr < min_budget_inr:
                continue

            # Filter by keyword query if present
            if clean_q:
                # Check for match in make, model, variant, key features, or colors
                match_text = f"{spec.make} {spec.model} {spec.variant} {' '.join(spec.key_features)} {' '.join(spec.colors_available)}".lower()
                
                # Check individual tokens
                tokens = clean_q.split()
                if not any(token in match_text for token in tokens):
                    continue

            results.append(spec)

        # Sort by relevance or price
        results.sort(key=lambda v: v.ex_showroom_price_inr)
        matched = results[:limit]
        return CatalogSearchResult(query=clean_q, vehicles=matched, total_matched=len(results))

    def search_from_user_text(self, text: str, limit: int = 3) -> List[VehicleSpec]:
        """Extracts intent and keywords from conversational text and retrieves matched vehicles.
        
        Optimized for <1ms in-memory lookup.
        """
        text_lower = text.lower()

        # Check for brand mentions
        found_make: Optional[str] = None
        for make in ["mercedes", "mercedes-benz", "benz", "bmw", "audi", "mahindra", "tata", "hyundai"]:
            if make in text_lower:
                found_make = "Mercedes-Benz" if "benz" in make or "mercedes" in make else make.title()
                break

        # Check for body type mentions
        found_body: Optional[BodyType] = None
        if "suv" in text_lower or "4x4" in text_lower:
            found_body = BodyType.SUV
        elif "sedan" in text_lower or "limousine" in text_lower:
            found_body = BodyType.SEDAN
        elif "ev" in text_lower or "electric" in text_lower:
            pass  # Handled in fuel type

        # Check for fuel type
        found_fuel: Optional[FuelType] = None
        if "electric" in text_lower or "ev" in text_lower:
            found_fuel = FuelType.ELECTRIC
        elif "diesel" in text_lower:
            found_fuel = FuelType.DIESEL
        elif "petrol" in text_lower:
            found_fuel = FuelType.PETROL

        # Extract budget (e.g. 1 cr, 1 crore, 70 lakh, 30 lakhs, 1.5 cr)
        max_budget: Optional[int] = None
        min_budget: Optional[int] = None

        is_under = any(kw in text_lower for kw in ["under", "below", "less than", "within", "up to", "maximum", "max"])
        is_above = any(kw in text_lower for kw in ["above", "more than", "at least", "starting from", "minimum", "min"])

        cr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:cr|crore|crores)", text_lower)
        if cr_match:
            cr_val = float(cr_match.group(1))
            val_inr = int(cr_val * 10_000_000)
            if is_under:
                max_budget = int(val_inr * 1.05)
                min_budget = None
            elif is_above:
                min_budget = int(val_inr * 0.95)
                max_budget = None
            else:
                max_budget = int(val_inr * 1.25)
                min_budget = int(val_inr * 0.60)

        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|l|lac|lacs)", text_lower)
        if lakh_match and not cr_match:
            lakh_val = float(lakh_match.group(1))
            val_inr = int(lakh_val * 100_000)
            if is_under:
                max_budget = int(val_inr * 1.05)
                min_budget = None
            elif is_above:
                min_budget = int(val_inr * 0.95)
                max_budget = None
            else:
                max_budget = int(val_inr * 1.25)
                min_budget = int(val_inr * 0.60)

        # Search with extracted parameters
        result = self.search(
            query=text_lower if not (found_make or found_body or max_budget) else None,
            make=found_make,
            body_type=found_body,
            fuel_type=found_fuel,
            max_budget_inr=max_budget,
            min_budget_inr=min_budget,
            limit=limit,
        )

        # If strict search returned nothing, fallback to brand search or top items
        if not result.vehicles:
            if found_make:
                result = self.search(make=found_make, limit=limit)
            elif found_body:
                result = self.search(body_type=found_body, limit=limit)

        return result.vehicles

    def format_rag_context(self, vehicles: List[VehicleSpec]) -> str:
        """Formats matched vehicles into an authoritative context block for the LLM system prompt."""
        if not vehicles:
            return ""

        lines = [
            "### Authoritative Dealership Live Inventory & Pricing (GROUND TRUTH):",
            "Use ONLY these official specifications, prices, and stock numbers. Do NOT invent different prices.",
        ]

        for v in vehicles:
            features_str = ", ".join(v.key_features[:4])
            colors_str = ", ".join(v.colors_available)
            lines.append(
                f"- **{v.make} {v.model} ({v.variant})** [{v.body_type.value}, {v.fuel_type.value}]: "
                f"{v.formatted_price_display} | Stock: {v.in_stock_units} units available | "
                f"Colors: {colors_str} | Features: {features_str}"
            )

        return "\n".join(lines)


# Global catalog service instance
catalog_service = CatalogService()
