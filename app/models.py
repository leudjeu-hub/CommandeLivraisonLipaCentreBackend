from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.database import Base


class Produkt(Base):
    __tablename__ = "produkte"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    preis = Column(Float, nullable=False)
    bestand = Column(Integer, default=0)


class Bestellung(Base):
    __tablename__ = "bestellungen"
    id = Column(Integer, primary_key=True)
    kunde_name = Column(String, nullable=False)
    telefon = Column(String, nullable=False)
    status = Column(String, default="neu")
    erstellt_am = Column(DateTime, default=datetime.utcnow)
    gesamt = Column(Float, default=0)
    positionen = relationship("Position", back_populates="bestellung")


class Position(Base):
    __tablename__ = "positionen"
    id = Column(Integer, primary_key=True)
    bestellung_id = Column(Integer, ForeignKey("bestellungen.id"))
    produkt_id = Column(Integer, ForeignKey("produkte.id"))
    menge = Column(Integer, nullable=False)
    einzelpreis = Column(Float, nullable=False)
    bestellung = relationship("Bestellung", back_populates="positionen")
    produkt = relationship("Produkt")
