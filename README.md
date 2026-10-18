# Papeterie API

Web-API (FastAPI + PostgreSQL) für die Bestell-App der Librairie Papeterie du Centre.

## Lokal starten

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # dann DATABASE_URL und SHOP_WHATSAPP eintragen
uvicorn app.main:app --reload
```

Danach im Browser: http://localhost:8000/docs

## Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET | /produkte/ | Alle Produkte |
| GET | /produkte/{id} | Ein Produkt |
| POST | /produkte/ | Produkt anlegen |
| PUT | /produkte/{id} | Produkt ändern |
| POST | /bestellungen/ | Bestellung anlegen (liefert `whatsapp_url`) |
| GET | /bestellungen/ | Alle Bestellungen |
| PATCH | /bestellungen/{id}/status | Status: neu, bestätigt, geliefert, storniert |

## Deployment auf Render

1. Repository auf GitHub hochladen.
2. Bei Render „New → Blueprint“ wählen und das Repo verbinden (nutzt `render.yaml`).
3. Umgebungsvariablen `DATABASE_URL` (von Neon) und `SHOP_WHATSAPP` (z. B. 2376XXXXXXXX, ohne +) eintragen.
