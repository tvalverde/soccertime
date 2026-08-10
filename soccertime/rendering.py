"""HTML for model images, kept out of the models themselves.

Both the templates and the admin need this markup, so it lives in one importable place
rather than on the model, which has no business emitting `<img>` tags.
"""

from django.utils.html import format_html
from django.utils.safestring import mark_safe

FALLBACK_SVG = mark_safe(  # noqa: S308 - a constant, no interpolation
    """
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-emoji-dizzy" viewBox="0 0 16 16">
      <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/>
      <path d="M9.146 5.146a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 0 1 .708.708l-.647.646.647.646a.5.5 0 0 1-.708.708l-.646-.647-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708m-5 0a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 1 1 .708.708l-.647.646.647.646a.5.5 0 1 1-.708.708L5.5 7.207l-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708M10 11a2 2 0 1 1-4 0 2 2 0 0 1 4 0"/>
    </svg>
    """
)


def image_markup(instance):
    """Render an instance's image, the placeholder when its file is missing, or nothing.

    Accepts None so callers can pass an optional relation — a competition without a flag,
    a favourite without a team — without guarding first. That case renders empty: the
    placeholder means "this should have had an image", and a competition that was never
    given a flag simply has none. Showing it there would put a broken-image icon next to
    every flagless competition.
    """
    if instance is None:
        return mark_safe("")

    image = instance.image_file
    if not image or not image.storage.exists(image.name):
        return FALLBACK_SVG

    width, height = instance.image_dimensions
    return format_html(
        '<img src="{}" width="{}" height="{}" />',
        image.url,
        width / instance.IMG_WIDTH_DIVISOR,
        height / instance.IMG_WIDTH_DIVISOR,
    )
