from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Produkt, Bestellung, Position
from app.schemas import BestellungNeu, StatusUpdate
from app.whatsapp import whatsapp_link

router = APIRouter()
ERLAUBTE_STATUS = {"neu", "bestätigt", "geliefert", "storniert"}


@router.post("/")
def bestellung_anlegen(b: BestellungNeu, db: Session = Depends(get_db)):
    bestellung = Bestellung(kunde_name=b.kunde_name, telefon=b.telefon)
    gesamt = 0
    for pos in b.positionen:
        produkt = db.get(Produkt, pos.produkt_id)
        if not produkt:
            raise HTTPException(404, f"Produkt {pos.produkt_id} nicht gefunden")
        if produkt.bestand < pos.menge:
            raise HTTPException(400, f"Nicht genug Bestand für {produkt.name}")
        produkt.bestand -= pos.menge
        gesamt += produkt.preis * pos.menge
        bestellung.positionen.append(
            Position(produkt=produkt, menge=pos.menge, einzelpreis=produkt.preis)
        )
    bestellung.gesamt = gesamt
    db.add(bestellung)
    db.commit()
    db.refresh(bestellung)
    return {
        "id": bestellung.id,
        "gesamt": gesamt,
        "status": bestellung.status,
        "whatsapp_url": whatsapp_link(bestellung),
    }


@router.get("/")
def bestellungen_liste(db: Session = Depends(get_db)):
    return db.query(Bestellung).order_by(Bestellung.erstellt_am.desc()).all()


@router.patch("/{bestellung_id}/status")
def status_aendern(bestellung_id: int, s: StatusUpdate, db: Session = Depends(get_db)):
    if s.status not in ERLAUBTE_STATUS:
        raise HTTPException(400, f"Status muss einer von {sorted(ERLAUBTE_STATUS)} sein")
    bestellung = db.get(Bestellung, bestellung_id)
    if not bestellung:
        raise HTTPException(404, "Bestellung nicht gefunden")
    bestellung.status = s.status
    db.commit()
    return {"id": bestellung.id, "status": bestellung.status}
