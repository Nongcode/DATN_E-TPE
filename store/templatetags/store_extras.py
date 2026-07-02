from decimal import Decimal, InvalidOperation
import re

from django import template


register = template.Library()


@register.filter
def vnd(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "0 đ"
    return f"{amount:,.0f} đ"


@register.filter
def markup_price(value, percent):
    try:
        amount = Decimal(value)
        ratio = Decimal(percent) / Decimal("100")
    except (InvalidOperation, TypeError, ValueError):
        return "0 đ"
    marked = amount * (Decimal("1") + ratio)
    return f"{marked:,.0f} đ"


def _parse_spec_line(line):
    line = re.sub(r"\s+", " ", line.strip())
    match = re.match(r"^([^:\t]+?)\s*[:\t]\s*(.+)$", line)
    if not match:
        return None
    label = match.group(1).strip(" :-")
    value = match.group(2).strip(" :-")
    if not label or not value:
        return None
    return label, value


@register.filter
def spec_rows(value):
    rows = []
    for line in str(value or "").splitlines():
        parsed = _parse_spec_line(line)
        if parsed:
            rows.append(parsed)
    return rows


@register.filter
def description_is_specs(value):
    lines = [line for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return False
    parsed_count = sum(1 for line in lines if _parse_spec_line(line))
    return parsed_count >= 2 and parsed_count >= len(lines) * 0.6


@register.filter
def description_text(value):
    paragraphs = []
    for line in str(value or "").splitlines():
        line = line.strip()
        if line and not _parse_spec_line(line):
            paragraphs.append(line)
    return "\n".join(paragraphs)
