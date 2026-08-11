"""What counts as an image this site is willing to store.

Shared by the downloader that fetches them and the model that writes them, because both
have to agree and neither is a good home for the other: the download path lives in a
management command, and a model importing from there would have the dependency backwards.
"""

import io

from PIL import Image, UnidentifiedImageError

# Decided by Pillow rather than by the URL or the content type, both of which are claims
# made by whoever served the file. SVG is deliberately absent: Pillow cannot decode it,
# nginx serves it as `image/svg+xml`, and a browser executes the scripts inside one that
# is opened directly — a stored `.svg` is stored XSS on this site's own origin.
FORMAT_EXTENSIONS = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg", "GIF": ".gif"}


class ImageRejected(Exception):
    """The bytes are not an image this site will store, for whatever reason."""


def read_image_format(buffer: io.BytesIO) -> str:
    """Return the format Pillow decodes, refusing anything outside the allowlist.

    This is the only trustworthy statement about the bytes. Django's
    `get_image_dimensions` answers `(None, None)` for content it cannot parse rather than
    raising, so without this nothing notices that a file is not an image at all: it is
    stored, under whatever extension the source URL happened to end in, and served back
    from this site's own origin.

    The buffer is rewound on the way out so the caller can still read it.
    """
    buffer.seek(0)
    try:
        with Image.open(buffer) as image:
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ImageRejected(f"is not a decodable image: {error}") from error
    finally:
        buffer.seek(0)
    if image_format not in FORMAT_EXTENSIONS:
        raise ImageRejected(f"decodes as {image_format}, which this site does not store")
    return image_format


def extension_for(image_bytes: io.BytesIO) -> str:
    """The filename extension the decoded content earns, never the one the URL claimed."""
    return FORMAT_EXTENSIONS[read_image_format(image_bytes)]
