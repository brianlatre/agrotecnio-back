from fastapi import FastAPI

from app.db import Base, engine
from app.api.api_v1.api import api_router
import app.models
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    # Crea las tablas si no existen (y el fichero sqlite)
    Base.metadata.create_all(bind=engine)


# Routers


@app.get("/", tags=["health"])
def read_root():
    return {"message": "ok"}