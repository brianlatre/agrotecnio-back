from __future__ import annotations

from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Slaughterhouse(Base):
    __tablename__ = "Slaughterhouses"

    slaughterhouse_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    capacity_per_day: Mapped[int] = mapped_column(Integer)
    price_per_kg: Mapped[float] = mapped_column(Float)

    # Rango de penalizaciones (para simular escenarios)
    penalty_15_min: Mapped[float] = mapped_column(Float)
    penalty_15_max: Mapped[float] = mapped_column(Float)
    penalty_20_min: Mapped[float] = mapped_column(Float)
    penalty_20_max: Mapped[float] = mapped_column(Float)

    def __repr__(self) -> str:
        return f"<Slaughterhouse id={self.slaughterhouse_id!r} name={self.name!r}>"
