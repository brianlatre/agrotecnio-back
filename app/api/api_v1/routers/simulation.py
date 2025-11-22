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

    route = Route(
        truck_type="20T",
        path=[
            [41.93, 2.25],
            [41.94, 2.26],
            [41.93, 2.25],
        ],
        stops=["F1"],
        pigs_transported=180,
        cost=45.50,
    )

    kpis = KPIs(
        daily_revenue=25000,
        daily_cost=1200,
        total_pigs=180,
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
            new_weight=112.9,
            pigs_remaining=0,
            status="visited",
        ),
    ]

    logs = [
        LogEntry(type="info", msg="Ruta 1 completada con éxito."),
        LogEntry(type="warning", msg="Penalización detectada en Granja F5."),
    ]

    return NextDayResponse(
        day_index=1,
        routes=[route],
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
