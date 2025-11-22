from __future__ import annotations

from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Farm(Base):
    __tablename__ = "Farms"

    farm_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    # Estado actual
    inventory_pigs: Mapped[int] = mapped_column(Integer)  # nº cerdos
    avg_weight_kg: Mapped[float] = mapped_column(Float)   # peso medio actual
    growth_rate_kg_per_week: Mapped[float] = mapped_column(Float)
    age_weeks: Mapped[int] = mapped_column(Integer)
    price_per_kg: Mapped[float] = mapped_column(Float)

    # Aquí podrías añadir en el futuro:
    # max_capacity_pigs, resource_consumption, etc.

    def __repr__(self) -> str:
        return f"<Farm id={self.farm_id!r} name={self.name!r}>"

    # ---- helpers de dominio (para la simulación) ----
    @property
    def is_in_optimal_weight_range(self) -> bool:
        return 105 <= self.avg_weight_kg <= 115

    def get_weight_penalty_ratio(self) -> float:
        """
        Devuelve el factor de penalización según peso:
        0.0 = sin penalización
        0.15 = penalización 15%
        0.20 = penalización 20%
        """
        w = self.avg_weight_kg
        if 105 <= w <= 115:
            return 0.0
        if 100 <= w <= 120:
            return 0.15
        return 0.20
