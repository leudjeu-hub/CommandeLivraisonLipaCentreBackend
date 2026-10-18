from pydantic import BaseModel


class ProduktNeu(BaseModel):
    name: str
    preis: float
    bestand: int = 0


class PositionNeu(BaseModel):
    produkt_id: int
    menge: int


class BestellungNeu(BaseModel):
    kunde_name: str
    telefon: str
    positionen: list[PositionNeu]


class StatusUpdate(BaseModel):
    status: str
