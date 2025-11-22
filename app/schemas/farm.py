from typing import Optional
from pydantic import BaseModel, ConfigDict


class FarmBase(BaseModel):
    name: str
    lat: float
    lon: float
    inventory_pigs: int
    avg_weight_kg: float
    growth_rate_kg_per_week: float
    age_weeks: int
    price_per_kg: float


class FarmCreate(FarmBase):
    # Si quieres que el backend genere el id → farm_id: Optional[str] = None
    farm_id: str


class FarmUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    inventory_pigs: Optional[int] = None
    avg_weight_kg: Optional[float] = None
    growth_rate_kg_per_week: Optional[float] = None
    age_weeks: Optional[int] = None
    price_per_kg: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class FarmRead(FarmBase):
    farm_id: str

    model_config = ConfigDict(from_attributes=True)
