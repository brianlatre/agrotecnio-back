from typing import Optional
from pydantic import BaseModel, ConfigDict


class TransportBase(BaseModel):
    type: str           # "small_truck" | "big_truck" ...
    capacity_tons: float
    cost_per_km: float
    max_hours_per_week: float
    fixed_weekly_cost: float
    available: bool


class TransportCreate(TransportBase):
    pass


class TransportUpdate(BaseModel):
    type: Optional[str] = None
    capacity_tons: Optional[float] = None
    cost_per_km: Optional[float] = None
    max_hours_per_week: Optional[float] = None
    fixed_weekly_cost: Optional[float] = None
    available: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class TransportRead(TransportBase):
    transport_id: str

    model_config = ConfigDict(from_attributes=True)
