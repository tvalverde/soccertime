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


FALLBACK_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-emoji-dizzy" viewBox="0 0 16 16">
  <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/>
  <path d="M9.146 5.146a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 0 1 .708.708l-.647.646.647.646a.5.5 0 0 1-.708.708l-.646-.647-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708m-5 0a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 1 1 .708.708l-.647.646.647.646a.5.5 0 1 1-.708.708L5.5 7.207l-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708M10 11a2 2 0 1 1-4 0 2 2 0 0 1 4 0"/>
</svg>
"""


@register.filter
def render_image_markup(obj):
    """Render HTML for an ImageMixin model instance or fallback SVG."""
    from django.utils.safestring import mark_safe

    if not obj:
        return mark_safe(FALLBACK_SVG)
    if hasattr(obj, "render_image"):
        return mark_safe(obj.render_image())
    return mark_safe(FALLBACK_SVG)
