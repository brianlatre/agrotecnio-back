from typing import List, Literal, Dict, Any
from pydantic import BaseModel


# ---------- /api/init ----------

class InitSlaughterhouse(BaseModel):
    id: str
    lat: float
    lng: float
    capacity: int


class InitFarm(BaseModel):
    id: str
    lat: float
    lng: float
    pigs: int
    avg_weight: float


class InitPrices(BaseModel):
    base: float
    diesel_s: float


class InitResponse(BaseModel):
    slaughterhouse: InitSlaughterhouse
    farms: List[InitFarm]
    prices: InitPrices
    simulation: Dict[str, Any]


# ---------- /api/simulation/next-day ----------

class NextDayRequest(BaseModel):
    # Lo dejamos por si más adelante quieres tunear growth_rate
    growth_rate: float = 0.9


class Route(BaseModel):
    truck_type: str
    path: List[List[float]]
    stops: List[str]
    pigs_transported: int
    cost: float


class KPIs(BaseModel):
    daily_revenue: float
    daily_cost: float
    total_pigs: int


class FarmUpdate(BaseModel):
    id: str
    new_weight: float
    pigs_remaining: int
    status: Literal["growing", "visited", "empty"]


class LogEntry(BaseModel):
    type: Literal["info", "warning", "error"]
    msg: str


class NextDayResponse(BaseModel):
    day_index: int
    routes: List[Route]
    kpis: KPIs
    farm_updates: List[FarmUpdate]
    logs: List[LogEntry]


# ---------- /api/simulation/reset ----------

class ResetResponse(BaseModel):
    ok: bool


# ---------- /api/simulation/history ----------

class HistoryResponse(BaseModel):
    labels: List[str]
    profit: List[float]
    revenue: List[float]
    cost: List[float]
    pigs_delivered: List[int]
