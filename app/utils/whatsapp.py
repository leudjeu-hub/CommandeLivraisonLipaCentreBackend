from urllib.parse import quote

from app.core.config import get_settings
from app.models.order import Order


def build_whatsapp_link(order: Order) -> str:
    settings = get_settings()
    lines = [
        f"New order #{order.id}",
        f"Customer: {order.customer_name} ({order.phone})",
        "",
    ]
    for item in order.items:
        lines.append(f"- {item.quantity} x {item.product.name} = {item.line_total:.0f} FCFA")
    lines.append(f"\nTotal: {order.total:.0f} FCFA")
    text = quote("\n".join(lines))
    return f"https://wa.me/{settings.shop_whatsapp}?text={text}"
