import re

from django import template

register = template.Library()


@register.filter
def sort_admin_menu_models(models):
    def sort_key(item):
        name = str(item.get("name", "")).strip()
        match = re.match(r"^(\d+)\.", name)
        if match:
            return (0, int(match.group(1)))
        return (1, name.casefold())

    return sorted(models, key=sort_key)
