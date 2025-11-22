from fastapi import APIRouter

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


# ---------- GET /api/init ----------

@router.get("/init", response_model=InitResponse)
def get_initial_state() -> InitResponse:
    slaughterhouse = InitSlaughterhouse(
        id="S1",
        lat=41.930,
        lng=2.254,
        capacity=2000,
    )

    farms = [
        InitFarm(
            id="F1",
            lat=41.94,
            lng=2.26,
            pigs=500,
            avg_weight=98.5,
        ),
        InitFarm(
            id="F2",
            lat=41.92,
            lng=2.24,
            pigs=600,
            avg_weight=112.0,
        ),
        InitFarm(
            id="F3",
            lat=41.95,
            lng=2.21,
            pigs=350,
            avg_weight=105.3,
        ),
        InitFarm(
            id="F4",
            lat=41.91,
            lng=2.28,
            pigs=420,
            avg_weight=118.7,
        ),
    ]

    prices = InitPrices(
        base=1.56,
        diesel_s=1.15,
    )

    return InitResponse(
        slaughterhouse=slaughterhouse,
        farms=farms,
        prices=prices,
    )


# ---------- POST /api/simulation/next-day ----------

@router.post("/simulation/next-day", response_model=NextDayResponse)
def simulate_next_day(payload: NextDayRequest) -> NextDayResponse:
    # Ruta 1: camión 20T, visita F1
    route1 = Route(
        truck_type="20T",
        path=[
            [41.93, 2.25],   # matadero
            [41.94, 2.26],   # F1
            [41.93, 2.25],   # matadero
        ],
        stops=["F1"],
        pigs_transported=180,
        cost=45.50,
    )

    # Ruta 2: camión 10T, visita F2 y F3
    route2 = Route(
        truck_type="10T",
        path=[
            [41.93, 2.25],   # matadero
            [41.92, 2.24],   # F2
            [41.95, 2.21],   # F3
            [41.93, 2.25],   # matadero
        ],
        stops=["F2", "F3"],
        pigs_transported=140,
        cost=38.20,
    )

    # KPIs (de ejemplo, agregando rutas)
    kpis = KPIs(
        daily_revenue=25000 + 14500,  # 2 rutas
        daily_cost=1200 + 900,
        total_pigs=180 + 140,
    )

    farm_updates = [
        FarmUpdate(
            id="F1",
            new_weight=99.4,
            pigs_remaining=320,
            status="growing",
        ),
        FarmUpdate(
            id="F2",
            new_weight=113.2,
            pigs_remaining=420,
            status="visited",
        ),
        FarmUpdate(
            id="F3",
            new_weight=106.1,
            pigs_remaining=210,
            status="visited",
        ),
        FarmUpdate(
            id="F4",
            new_weight=119.5,
            pigs_remaining=420,
            status="growing",
        ),
    ]

    logs = [
        LogEntry(type="info", msg="Ruta 1 completada con éxito (F1)."),
        LogEntry(type="info", msg="Ruta 2 completada con éxito (F2 → F3)."),
        LogEntry(type="warning", msg="Penalización detectada en Granja F4 (peso fuera de rango)."),
    ]

    return NextDayResponse(
        day_index=1,
        routes=[route1, route2],
        kpis=kpis,
        farm_updates=farm_updates,
        logs=logs,
    )


# ---------- POST /api/simulation/reset ----------

@router.post("/simulation/reset", response_model=ResetResponse)
def reset_simulation() -> ResetResponse:
    return ResetResponse(
        ok=True,
    )


# ---------- GET /api/simulation/history ----------

@router.get("/simulation/history", response_model=HistoryResponse)
def get_simulation_history() -> HistoryResponse:
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
