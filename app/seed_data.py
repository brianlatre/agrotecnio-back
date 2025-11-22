import uuid

from sqlalchemy.orm import Session

from app.db import SessionLocal, Base, engine
from app.models.farm import Farm
from app.models.slaughterhouse import Slaughterhouse
from app.models.transport import Transport


def create_tables() -> None:
    # Por si el esquema no está creado aún
    Base.metadata.create_all(bind=engine)


def seed_slaughterhouses(db: Session) -> None:
    if db.query(Slaughterhouse).count() > 0:
        return

    s1 = Slaughterhouse(
        slaughterhouse_id="S1",
        name="Escorxador Central de Catalunya",
        lat=41.930,
        lon=2.254,
        capacity_per_day=2000,
        price_per_kg=1.56,
        penalty_15_min=0.10,
        penalty_15_max=0.20,
        penalty_20_min=0.20,
        penalty_20_max=0.30,
    )

    db.add(s1)
    db.commit()


def seed_farms(db: Session) -> None:
    if db.query(Farm).count() > 0:
        return

    farms = [
        Farm(
            farm_id="F1",
            name="Granja del Nord",
            lat=41.94,
            lon=2.26,
            inventory_pigs=500,
            avg_weight_kg=98.5,
            growth_rate_kg_per_week=6.3,
            age_weeks=18,
            price_per_kg=1.50,
        ),
        Farm(
            farm_id="F2",
            name="Granja del Sud",
            lat=41.92,
            lon=2.24,
            inventory_pigs=600,
            avg_weight_kg=112.0,
            growth_rate_kg_per_week=6.1,
            age_weeks=19,
            price_per_kg=1.52,
        ),
        Farm(
            farm_id="F3",
            name="Can Porc",
            lat=41.95,
            lon=2.21,
            inventory_pigs=350,
            avg_weight_kg=105.3,
            growth_rate_kg_per_week=5.8,
            age_weeks=17,
            price_per_kg=1.49,
        ),
        Farm(
            farm_id="F4",
            name="Masia del Riu",
            lat=41.91,
            lon=2.28,
            inventory_pigs=420,
            avg_weight_kg=118.7,
            growth_rate_kg_per_week=6.0,
            age_weeks=20,
            price_per_kg=1.51,
        ),
    ]

    db.add_all(farms)
    db.commit()


def seed_transports(db: Session) -> None:
    if db.query(Transport).count() > 0:
        return

    # Camión pequeño 10T
    t_small = Transport(
        transport_id=str(uuid.uuid4()),
        type="small_truck_10T",
        capacity_tons=10.0,
        cost_per_km=1.15,
        max_hours_per_week=40.0,
        fixed_weekly_cost=2000.0,
        available=True,
    )

    # Camión grande 20T
    t_big = Transport(
        transport_id=str(uuid.uuid4()),
        type="big_truck_20T",
        capacity_tons=20.0,
        cost_per_km=1.25,
        max_hours_per_week=40.0,
        fixed_weekly_cost=2500.0,
        available=True,
    )

    db.add_all([t_small, t_big])
    db.commit()


def main() -> None:
    create_tables()
    db = SessionLocal()
    try:
        seed_slaughterhouses(db)
        seed_farms(db)
        seed_transports(db)
        print("✅ Seed completado: slaughterhouses, farms y transports.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
