import os

from django.template.defaulttags import register


@register.filter
def env(key, default=""):
    value = os.environ.get(key)
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
    return value or default


@register.filter
def sort_by_list_length(regroup_list, reverse="True"):
    """Ordena una lista de resultados de regroup por la longitud de su 'list'.

    Por defecto ordena de mayor a menor (reverse=True).
    Uso: {% regroup items by field as grouped %}{{ grouped|sort_by_list_length }}
    """
    reverse_bool = str(reverse).lower() not in ("false", "0", "")
    items = list(regroup_list)
    return sorted(items, key=lambda x: len(x.list), reverse=reverse_bool)


@register.filter
def normalize_subcategory(value):
    """Normaliza un valor de subcategoría para comparaciones y querystrings.

    Convierte None o cadenas vacías a una cadena vacía para mantener consistencia.
    """
    if value is None or value == "":
        return ""
    return str(value)


@register.filter
def sort_categories_by_total_links(regroup_list, reverse="True"):
    """Ordena categorías por el total de enlaces sumando todos los canales.

    Cada categoría contiene canales (agrupados por name), y cada canal tiene N enlaces.
    Este filtro suma todos los enlaces de todos los canales de cada categoría.
    """
    reverse_bool = str(reverse).lower() not in ("false", "0", "")
    items = list(regroup_list)

    def count_total_links(category_group):
        # category_group.list contiene los ChannelLink objects de esa categoría
        # Cada ChannelLink es un enlace individual, así que el total es len(list)
        return len(category_group.list)

    return sorted(items, key=count_total_links, reverse=reverse_bool)
