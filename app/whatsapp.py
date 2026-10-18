import os
from urllib.parse import quote

SHOP_NUMMER = os.environ.get("SHOP_WHATSAPP", "2376XXXXXXXX")


def whatsapp_link(bestellung):
    zeilen = [
        f"Neue Bestellung Nr. {bestellung.id}",
        f"Kunde: {bestellung.kunde_name} ({bestellung.telefon})",
        "",
    ]
    for pos in bestellung.positionen:
        zeilen.append(
            f"- {pos.menge} x {pos.produkt.name} = {pos.menge * pos.einzelpreis:.0f} FCFA"
        )
    zeilen.append(f"\nGesamt: {bestellung.gesamt:.0f} FCFA")
    return f"https://wa.me/{SHOP_NUMMER}?text={quote(chr(10).join(zeilen))}"
