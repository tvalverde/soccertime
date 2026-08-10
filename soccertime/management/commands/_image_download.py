"""Image fetching shared by the commands that populate flags and crests."""

import io
from collections.abc import Callable

import requests

IMAGE_DOWNLOAD_TIMEOUT = 10


def download_image(url: str | None, on_error: Callable[[str], object] | None = None) -> io.BytesIO | None:
    """Download an image, returning None when the URL is missing or unreachable.

    A failure is reported through `on_error` and skipped rather than raised: one bad
    image must never abort a scraping run halfway through.
    """
    if not url:
        return None
    try:
        response = requests.get(url, stream=True, timeout=IMAGE_DOWNLOAD_TIMEOUT)
    except requests.RequestException as error:
        if on_error:
            on_error(f"Could not download image from {url}: {error}")
        return None
    if response.status_code != 200:
        return None
    return io.BytesIO(response.content)
