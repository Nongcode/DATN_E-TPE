from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def vnd(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "0 d"
    return f"{amount:,.0f} d"


@register.filter
def markup_price(value, percent):
    try:
        amount = Decimal(value)
        ratio = Decimal(percent) / Decimal("100")
    except (InvalidOperation, TypeError, ValueError):
        return "0 d"
    marked = amount * (Decimal("1") + ratio)
    return f"{marked:,.0f} d"
