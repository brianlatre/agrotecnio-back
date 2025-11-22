import math
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.farm import Farm
from app.models.slaughterhouse import Slaughterhouse
from app.models.transport import Transport
from app.schemas.simulation import (
    InitResponse,
    InitSlaughterhouse,
    InitFarm,
    InitPrices,
    NextDayRequest,
    NextDayResponse,
    Route,
    KPIs,
    FarmUpdate,
    LogEntry,
    ResetResponse,
    HistoryResponse,
)

router = APIRouter(tags=["simulation"])

# Día actual de simulación (estado en memoria, simple)
CURRENT_DAY_INDEX = 0


# ---------- helpers internos ----------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia entre dos puntos en km."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def penalty_ratio(weight: float) -> float:
    """
    0.0 sin penalización  (105–115 kg)
    0.15 penalización     (100–120 kg fuera del rango ideal)
    0.20 penalización     (<100 o >120)
    """
    if 105 <= weight <= 115:
        return 0.0
    if 100 <= weight <= 120:
        return 0.15
    return 0.20


# ---------- GET /api/init ----------

@router.get("/init", response_model=InitResponse)
def get_initial_state(db: Session = Depends(get_db)) -> InitResponse:
    slaughterhouse = db.query(Slaughterhouse).first()
    if not slaughterhouse:
        raise HTTPException(status_code=500, detail="No hay mataderos en la base de datos")

    farms = db.query(Farm).all()
    if not farms:
        raise HTTPException(status_code=500, detail="No hay granjas en la base de datos")

    slaughterhouse_data = InitSlaughterhouse(
        id=slaughterhouse.slaughterhouse_id,
        lat=slaughterhouse.lat,
        lng=slaughterhouse.lon,
        capacity=slaughterhouse.capacity_per_day,
    )

    farms_data = [
        InitFarm(
            id=farm.farm_id,
            lat=farm.lat,
            lng=farm.lon,
            pigs=farm.inventory_pigs,
            avg_weight=farm.avg_weight_kg,
        )
        for farm in farms
    ]

    # precio base por kg desde el matadero; si no, fallback
    base_price = slaughterhouse.price_per_kg or 1.56

    # un transport “small” para coger diesel_s; si no hay, fallback
    small_truck = (
        db.query(Transport)
        .order_by(Transport.capacity_tons.asc())
        .first()
    )
    diesel_s = small_truck.cost_per_km if small_truck else 1.15

    prices = InitPrices(
        base=base_price,
        diesel_s=diesel_s,
    )

    return InitResponse(
        slaughterhouse=slaughterhouse_data,
        farms=farms_data,
        prices=prices,
    )


# ---------- POST /api/simulation/next-day ----------

@router.post("/simulation/next-day", response_model=NextDayResponse)
def simulate_next_day(
    payload: NextDayRequest,
    db: Session = Depends(get_db),
) -> NextDayResponse:
    global CURRENT_DAY_INDEX

    slaughterhouse = db.query(Slaughterhouse).first()
    if not slaughterhouse:
        raise HTTPException(status_code=500, detail="No hay mataderos en la base de datos")

    transports = db.query(Transport).all()
    if not transports:
        raise HTTPException(status_code=500, detail="No hay camiones en la base de datos")

    farms = db.query(Farm).filter(Farm.inventory_pigs > 0).all()
    if not farms:
        raise HTTPException(status_code=400, detail="No hay cerdos disponibles en ninguna granja")

    # 1) Aumentar peso de todos los cerdos (crecimiento diario aproximado)
    growth = payload.growth_rate
    for farm in farms:
        farm.avg_weight_kg += growth

    # 2) Seleccionar granjas priorizando rango óptimo 105–115 kg
    def farm_priority(f: Farm) -> tuple:
        in_opt = 105 <= f.avg_weight_kg <= 115
        dist_to_ideal = abs(f.avg_weight_kg - 110)
        # Orden: primero en rango óptimo (True > False), luego menor distancia al ideal, luego más cerdos
        return (not in_opt, dist_to_ideal, -f.inventory_pigs)

    farms_sorted = sorted(farms, key=farm_priority)

    # 3) Capacidad diaria del matadero (en nº de cerdos)
    remaining_capacity = slaughterhouse.capacity_per_day

    # 4) Usamos el camión de mayor capacidad para las rutas
    transports_sorted = sorted(transports, key=lambda t: t.capacity_tons, reverse=True)
    main_truck = transports_sorted[0]
    truck_capacity_kg = main_truck.capacity_tons * 1000

    routes: List[Route] = []
    shipped_by_farm: Dict[str, int] = {}

    # agrupamos granjas en grupos de 3 máximo
    for i in range(0, len(farms_sorted), 3):
        if remaining_capacity <= 0:
            break

        group = farms_sorted[i:i+3]

        # capacidad de este viaje en nº de cerdos
        # usamos peso medio del grupo para estimar
        avg_group_weight = sum(f.avg_weight_kg for f in group) / len(group)
        truck_capacity_pigs = int(truck_capacity_kg / max(avg_group_weight, 1.0))

        truck_remaining_pigs = min(truck_capacity_pigs, remaining_capacity)
        if truck_remaining_pigs <= 0:
            break

        route_farms = []
        total_pigs_this_route = 0

        for farm in group:
            if truck_remaining_pigs <= 0 or remaining_capacity <= 0:
                break

            if farm.inventory_pigs <= 0:
                continue

            pigs_to_take = min(farm.inventory_pigs, truck_remaining_pigs, remaining_capacity)
            if pigs_to_take <= 0:
                continue

            # actualizar inventario en memoria
            farm.inventory_pigs -= pigs_to_take
            truck_remaining_pigs -= pigs_to_take
            remaining_capacity -= pigs_to_take
            total_pigs_this_route += pigs_to_take

            shipped_by_farm[farm.farm_id] = shipped_by_farm.get(farm.farm_id, 0) + pigs_to_take
            route_farms.append(farm)

        if total_pigs_this_route <= 0:
            continue

        # path del viaje: matadero -> granjas visitadas -> matadero
        path_coords = [[slaughterhouse.lat, slaughterhouse.lon]]
        for f in route_farms:
            path_coords.append([f.lat, f.lon])
        path_coords.append([slaughterhouse.lat, slaughterhouse.lon])

        # distancia total
        total_distance_km = 0.0
        for j in range(len(path_coords) - 1):
            lat1, lon1 = path_coords[j]
            lat2, lon2 = path_coords[j + 1]
            total_distance_km += haversine_km(lat1, lon1, lat2, lon2)

        cost = total_distance_km * main_truck.cost_per_km

        routes.append(
            Route(
                truck_type=f"{int(main_truck.capacity_tons)}T",
                path=path_coords,
                stops=[f.farm_id for f in route_farms],
                pigs_transported=total_pigs_this_route,
                cost=round(cost, 2),
            )
        )

    # 5) Persistir cambios en inventarios y pesos
    db.commit()

    # 6) Construir farm_updates
    farm_updates: List[FarmUpdate] = []
    for farm in db.query(Farm).all():
        if farm.inventory_pigs == 0:
            status = "empty"
        elif farm.farm_id in shipped_by_farm:
            status = "visited"
        else:
            status = "growing"

        farm_updates.append(
            FarmUpdate(
                id=farm.farm_id,
                new_weight=farm.avg_weight_kg,
                pigs_remaining=farm.inventory_pigs,
                status=status,
            )
        )

    # 7) KPIs: revenue y costes
    price_per_kg = slaughterhouse.price_per_kg or 1.56
    total_pigs = sum(shipped_by_farm.values())

    daily_revenue = 0.0
    for farm_id, pigs_sent in shipped_by_farm.items():
        farm = db.query(Farm).filter(Farm.farm_id == farm_id).first()
        if not farm:
            continue
        w = farm.avg_weight_kg
        ratio = penalty_ratio(w)
        total_kg = pigs_sent * w
        daily_revenue += total_kg * price_per_kg * (1 - ratio)

    daily_cost = sum(r.cost for r in routes)

    kpis = KPIs(
        daily_revenue=round(daily_revenue, 2),
        daily_cost=round(daily_cost, 2),
        total_pigs=total_pigs,
    )

    # 8) Logs
    logs: List[LogEntry] = []
    for idx, r in enumerate(routes, start=1):
        logs.append(
            LogEntry(
                type="info",
                msg=f"Ruta {idx} completada con éxito ({', '.join(r.stops)}).",
            )
        )

    for farm_update in farm_updates:
        ratio = penalty_ratio(farm_update.new_weight)
        if ratio > 0:
            logs.append(
                LogEntry(
                    type="warning",
                    msg=f"Penalización de {int(ratio * 100)}% en Granja {farm_update.id} (peso medio {farm_update.new_weight:.1f} kg).",
                )
            )

    # 9) Actualizar índice de día
    CURRENT_DAY_INDEX += 1

    return NextDayResponse(
        day_index=CURRENT_DAY_INDEX,
        routes=routes,
        kpis=kpis,
        farm_updates=farm_updates,
        logs=logs,
    )


# ---------- POST /api/simulation/reset ----------

@router.post("/simulation/reset", response_model=ResetResponse)
def reset_simulation() -> ResetResponse:
    # De momento solo confirmamos el reset; más adelante podemos restaurar
    # inventarios/pesos desde un snapshot inicial.
    global CURRENT_DAY_INDEX
    CURRENT_DAY_INDEX = 0
    return ResetResponse(ok=True)


# ---------- GET /api/simulation/history ----------

@router.get("/simulation/history", response_model=HistoryResponse)
def get_simulation_history() -> HistoryResponse:
    # Dummy mientras no tengamos tabla de histórico:
    labels = ["Día 1", "Día 2", "Día 3"]
    profit = [1000.0, 2500.0, 3200.0]
    revenue = [5000.0, 7000.0, 8000.0]
    cost = [4000.0, 4500.0, 4800.0]
    pigs_delivered = [180, 350, 420]

    return HistoryResponse(
        labels=labels,
        profit=profit,
        revenue=revenue,
        cost=cost,
        pigs_delivered=pigs_delivered,
    )
