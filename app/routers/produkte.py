from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Produkt
from app.schemas import ProduktNeu

router = APIRouter()


@router.get("/")
def produkte_liste(db: Session = Depends(get_db)):
    return db.query(Produkt).order_by(Produkt.name).all()


@router.get("/{produkt_id}")
def produkt_holen(produkt_id: int, db: Session = Depends(get_db)):
    produkt = db.get(Produkt, produkt_id)
    if not produkt:
        raise HTTPException(404, "Produkt nicht gefunden")
    return produkt


@router.post("/")
def produkt_anlegen(p: ProduktNeu, db: Session = Depends(get_db)):
    neu = Produkt(**p.model_dump())
    db.add(neu)
    db.commit()
    db.refresh(neu)
    return neu


@router.put("/{produkt_id}")
def produkt_aendern(produkt_id: int, p: ProduktNeu, db: Session = Depends(get_db)):
    produkt = db.get(Produkt, produkt_id)
    if not produkt:
        raise HTTPException(404, "Produkt nicht gefunden")
    for feld, wert in p.model_dump().items():
        setattr(produkt, feld, wert)
    db.commit()
    db.refresh(produkt)
    return produkt
