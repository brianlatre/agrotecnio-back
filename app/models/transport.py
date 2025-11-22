from __future__ import annotations

from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Transport(Base):
    __tablename__ = "Transports"

    transport_id: Mapped[str] = mapped_column(String, primary_key=True)

    # En BD la columna es "type"; aquí también, aunque pise el builtin de Python
    type: Mapped[str] = mapped_column(String)  # "small_truck", "big_truck", etc.

    capacity_tons: Mapped[float] = mapped_column(Float)
    cost_per_km: Mapped[float] = mapped_column(Float)
    max_hours_per_week: Mapped[float] = mapped_column(Float)
    fixed_weekly_cost: Mapped[float] = mapped_column(Float)
    available: Mapped[bool] = mapped_column(Boolean)

    def __repr__(self) -> str:
        return f"<Transport id={self.transport_id!r} type={self.type!r}>"

    @property
    def capacity_kg(self) -> float:
        return self.capacity_tons * 1000.0
