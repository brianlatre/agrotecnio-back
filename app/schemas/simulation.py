from typing import List, Optional
from pydantic import BaseModel, ConfigDict


# ---------- Entrada simulación ----------

class SimulationStartRequest(BaseModel):
    days: int = 10  # 2 semanas laborales
    start_day_index: int = 1  # por si quieres numerar 1..10
    slaughterhouse_id: Optional[str] = None  # si quieres elegir uno concreto


class SimulationStartResponse(BaseModel):
    simulation_id: str
    days_planned: int


# ---------- Plan diario ----------

class RouteStop(BaseModel):
    farm_id: str
    farm_name: str
    pigs_loaded: int
    avg_weight_kg: float
    distance_from_prev_km: float
    travel_time_hours: float
    penalty_ratio: float  # 0.0, 0.15 o 0.20
    revenue_eur: float
    penalty_cost_eur: float


class TruckRoute(BaseModel):
    transport_id: str
    truck_type: str  # small / big
    total_distance_km: float
    total_travel_time_hours: float
    total_load_kg: float
    cost_variable_eur: float
    cost_fixed_eur: float
    route: List[RouteStop]


class DailyPlan(BaseModel):
    simulation_id: str
    day_index: int
    slaughterhouse_id: str

    total_pigs_delivered: int
    total_kg_delivered: float
    capacity_used_pct: float  # % capacidad matadero

    routes: List[TruckRoute]


# ---------- KPIs acumulados ----------

class CumulativeStats(BaseModel):
    simulation_id: str

    total_pigs_delivered: int
    total_kg_delivered: float

    total_revenue_eur: float
    total_penalties_eur: float
    total_transport_cost_eur: float
    total_fixed_truck_cost_eur: float

    margin_eur: float
    margin_per_kg_eur: float

    # opcional: huella de carbono
    total_distance_km: float
    co2_kg: Optional[float] = None

    model_config = ConfigDict(from_attributes=False)
