from typing import Optional
from pydantic import BaseModel, ConfigDict


class SlaughterhouseBase(BaseModel):
    name: str
    lat: float
    lon: float
    capacity_per_day: int
    price_per_kg: float
    penalty_15_min: float
    penalty_15_max: float
    penalty_20_min: float
    penalty_20_max: float


class SlaughterhouseCreate(SlaughterhouseBase):
    pass


class SlaughterhouseUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    capacity_per_day: Optional[int] = None
    price_per_kg: Optional[float] = None
    penalty_15_min: Optional[float] = None
    penalty_15_max: Optional[float] = None
    penalty_20_min: Optional[float] = None
    penalty_20_max: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class SlaughterhouseRead(SlaughterhouseBase):
    slaughterhouse_id: str

    model_config = ConfigDict(from_attributes=True)
