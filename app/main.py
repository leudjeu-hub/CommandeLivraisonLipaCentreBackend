from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401  (registriert die Tabellen)
from app.routers import produkte, bestellungen

Base.metadata.create_all(engine)

app = FastAPI(title="Papeterie API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(produkte.router, prefix="/produkte", tags=["Produkte"])
app.include_router(bestellungen.router, prefix="/bestellungen", tags=["Bestellungen"])


@app.get("/", tags=["Status"])
def status():
    return {"status": "ok", "app": "Papeterie API"}
