import urllib.parse
from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

# --- מודלי קליטת דרישות הלקוח ---

class Child(BaseModel):
    age: int = Field(..., ge=0, le=17)

class Travelers(BaseModel):
    adults_count: int = Field(default=1, ge=1)
    children: List[Child] = Field(default_factory=list)
    accessibility_needs: Optional[str] = None

class TripOverview(BaseModel):
    destination: str = Field(..., min_length=2)
    start_date: date
    end_date: date
    flexible_dates: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> "TripOverview":
        if self.end_date < self.start_date:
            raise ValueError("תאריך הסיום חייב לחול ביום תאריך ההתחלה או לאחריו")
        return self

class Budget(BaseModel):
    currency: Literal["USD", "EUR", "ILS", "GBP"] = "USD"
    daily_budget_per_person: float = Field(default=80.0, gt=0)

InterestType = Literal[
    "history_and_culture",
    "culinary_and_food_tours",
    "nature_and_hiking",
    "kid_friendly_attractions",
    "shopping",
    "nightlife",
    "art_and_museums",
    "relaxation_and_wellness"
]

class PacingAndStyle(BaseModel):
    pace: Literal["relaxed", "moderate", "intense"] = "moderate"
    primary_interests: List[InterestType] = Field(default_factory=lambda: ["history_and_culture"])
    max_walking_km_per_day: Optional[float] = None

class Transportation(BaseModel):
    preferred_mode: Literal["walking_and_public_transit", "rental_car", "taxis_only", "mix"] = "walking_and_public_transit"
    willing_to_drive: bool = False

DietaryType = Literal["kosher", "vegetarian", "vegan", "gluten_free", "halal", "none"]

class ConstraintsAndPreferences(BaseModel):
    dietary_restrictions: List[DietaryType] = Field(default_factory=lambda: ["none"])
    shabbat_observer: bool = False
    must_visit_places: List[str] = Field(default_factory=list)
    places_to_avoid: List[str] = Field(default_factory=list)

class ClientTravelRequirements(BaseModel):
    trip_overview: TripOverview
    travelers: Travelers = Field(default_factory=Travelers)
    budget: Budget = Field(default_factory=Budget)
    pacing_and_style: PacingAndStyle = Field(default_factory=PacingAndStyle)
    transportation: Transportation = Field(default_factory=Transportation)
    constraints_and_preferences: ConstraintsAndPreferences = Field(default_factory=ConstraintsAndPreferences)

# --- מודלי פלט תוכנית הטיול ---

class DayItinerary(BaseModel):
    day_number: int
    title: str
    origin: str
    stops: List[str]
    destination: str
    travel_mode: str = "walking"
    daily_cost_estimate: float = Field(..., description="עלות יומית מוערכת לאדם כולל כלכלה ואטרקציות")
    summary: str
    maps_url: Optional[str] = None

class TripItinerary(BaseModel):
    destination: str
    total_days: int
    currency: str
    days: List[DayItinerary]

# --- מודל סיווג העברה לנציג אנושי ---

class TriageResult(BaseModel):
    needs_human: bool
    reason: str

# פונקציית עזר ליצירת קישורי ניווט ב-Google Maps
def generate_maps_url(origin: str, stops: List[str], destination: str, travel_mode: str = "walking") -> str:
    base_url = "https://www.google.com/maps/dir/?api=1"
    encoded_origin = urllib.parse.quote(origin)
    encoded_destination = urllib.parse.quote(destination)
    params = f"&origin={encoded_origin}&destination={encoded_destination}&travelmode={travel_mode}"
    if stops:
        encoded_waypoints = urllib.parse.quote("|".join(stops))
        params += f"&waypoints={encoded_waypoints}"
    return f"{base_url}{params}"