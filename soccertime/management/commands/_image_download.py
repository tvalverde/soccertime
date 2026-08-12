"""Image fetching shared by the commands that populate flags and crests.

Every URL reaching this module came out of scraped HTML, so it is attacker-influenced
input rather than configuration. The guards below are ordered by what they cost: the
scheme is free, the address needs a DNS lookup, the size needs the body, and decoding the
image needs all of it. Each one exists because the layer after it cannot be trusted to
catch what the layer before it let through — the content type in particular is only the
remote server's claim about what it sent, which is why the format is decided by decoding.
"""

import io
import ipaddress
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import requests_cache
import urllib3.util.connection

from soccertime.images import ImageRejected, read_image_format

# Per read, not for the whole transfer: a server dripping a byte at a time resets it
# forever, which is what DOWNLOAD_DEADLINE is for.
IMAGE_DOWNLOAD_TIMEOUT = 10
DOWNLOAD_DEADLINE = 30

ALLOWED_SCHEMES = frozenset({"http", "https"})

# The largest image in production is 1322 bytes, so this leaves three orders of magnitude
# of headroom while keeping a hostile response from filling a 512 MB container.
MAX_IMAGE_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 8192

MAX_REDIRECTS = 3


def _reject_unroutable_host(url: str) -> str:
    """Vet a URL's host and return the exact address the fetch must connect to.

    The container shares a network with Traefik and the other services on the host, so an
    unchecked fetch is a way to reach them from outside — the request originates inside
    the perimeter even though the URL came from a scraped page.

    Every address a name resolves to is checked, not just the first: a host answering with
    both a public and a private record would otherwise pass on whichever came back first.

    Returning the address, not just passing or raising, is what closes the rebinding hole.
    The name used to be resolved twice — here, and again by `requests` when it connected —
    with nothing forcing the two to agree, so a short-TTL DNS could answer public to the
    check and internal to the fetch. The caller pins the connection to the address returned
    here, so the name is never resolved a second time.
    """
    host = urlparse(url).hostname
    if not host:
        raise ImageRejected(f"no host in {url}")
    try:
        resolved = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError) as error:
        # Not just `socket.gaierror`: a hostname with an over-long label raises
        # `UnicodeError` from the IDNA encoder, and these names come from scraped HTML,
        # where a malformed one is ordinary. Either way it must be a skipped image rather
        # than the end of the run.
        raise ImageRejected(f"could not resolve {host}: {error}") from error
    if not resolved:
        raise ImageRejected(f"{host} resolves to nothing")
    for info in resolved:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_reserved:
            raise ImageRejected(f"{host} resolves to the non-public address {address}")
    # Every address passed the same check, so any of them is safe to connect to; the first
    # is the one the fetch is pinned to.
    return str(resolved[0][4][0])


@contextmanager
def _connect_only_to(ip: str) -> Iterator[None]:
    """Force every socket opened in this block to the vetted address.

    `create_connection` is urllib3's single choke point for opening a socket, and it is
    handed `(host, port)` — the *name*, which it would otherwise resolve itself, undoing the
    check above. Rewriting the host to the vetted IP means the connection goes where the
    check looked, and nowhere else; the name still travels through `requests` for the Host
    header and the TLS SNI, so certificate validation is unchanged.

    The hook is process-global, swapped for the duration of one request and restored in
    `finally`. That is safe because the scraper is a single sequential process — if it is
    ever parallelised, this needs a per-connection mechanism (a mounted adapter) instead.
    """
    original = urllib3.util.connection.create_connection

    def pinned(address: tuple[str, int], *args: Any, **kwargs: Any) -> socket.socket:
        _host, port = address
        return original((ip, port), *args, **kwargs)

    urllib3.util.connection.create_connection = pinned
    try:
        yield
    finally:
        urllib3.util.connection.create_connection = original


def _read_capped(response: requests.Response, deadline: float) -> bytes:
    """Read the body, giving up rather than trusting it to end.

    `response.content` reads to completion whatever the length, which is what made a
    single hostile URL enough to exhaust the container's memory.
    """
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise ImageRejected(f"declares {declared} bytes, over the {MAX_IMAGE_BYTES} limit")

    body = bytearray()
    for chunk in response.iter_content(CHUNK_SIZE):
        body.extend(chunk)
        if len(body) > MAX_IMAGE_BYTES:
            raise ImageRejected(f"body exceeds the {MAX_IMAGE_BYTES} byte limit")
        if time.monotonic() > deadline:
            raise ImageRejected(f"still arriving after {DOWNLOAD_DEADLINE}s")
    return bytes(body)


def _fetch(url: str, deadline: float) -> requests.Response:
    """Fetch `url`, following redirects one at a time so each destination is checked.

    Leaving redirects to `requests` is what would undo the address check: the URL that was
    vetted is not the URL that ends up being fetched.
    """
    for _ in range(MAX_REDIRECTS + 1):
        vetted_ip = _reject_unroutable_host(url)
        with _connect_only_to(vetted_ip):
            response = requests.get(
                url,
                stream=True,
                timeout=IMAGE_DOWNLOAD_TIMEOUT,
                allow_redirects=False,
            )
        if not response.is_redirect:
            return response
        location = response.headers.get("Location")
        response.close()
        if not location:
            raise ImageRejected(f"redirect from {url} carries no Location")
        url = urljoin(url, location)
        if urlparse(url).scheme not in ALLOWED_SCHEMES:
            raise ImageRejected(f"redirected to the disallowed scheme in {url}")
        if time.monotonic() > deadline:
            raise ImageRejected(f"still redirecting after {DOWNLOAD_DEADLINE}s")
    raise ImageRejected(f"more than {MAX_REDIRECTS} redirects from {url}")


def download_image(url: str | None, on_error: Callable[[str], object] | None = None) -> io.BytesIO | None:
    """Download an image, returning None when the URL is missing, unreachable or refused.

    A failure is reported through `on_error` and skipped rather than raised: one bad
    image must never abort a scraping run halfway through.

    The request deliberately bypasses the shared HTTP cache. `scrapit` installs it
    globally through `futbolenlatv.get_events()` before any image is fetched, and a cache
    reads the whole body in order to store it, which would leave the size limit here doing
    nothing. Nothing is lost: both callers already skip the download when the file is
    present in storage.
    """
    if not url:
        return None
    if urlparse(url).scheme not in ALLOWED_SCHEMES:
        if on_error:
            on_error(f"Refused image URL with a disallowed scheme: {url[:100]}")
        return None

    deadline = time.monotonic() + DOWNLOAD_DEADLINE
    try:
        with requests_cache.disabled():
            response = _fetch(url, deadline)
            try:
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if not content_type.split(";")[0].strip().lower().startswith("image/"):
                    raise ImageRejected(f"served {content_type or 'no content type'}")
                body = _read_capped(response, deadline)
            finally:
                response.close()
    except requests.RequestException as error:
        if on_error:
            on_error(f"Could not download image from {url}: {error}")
        return None
    except ImageRejected as error:
        if on_error:
            on_error(f"Refused image from {url}: {error}")
        return None

    buffer = io.BytesIO(body)
    try:
        read_image_format(buffer)
    except ImageRejected as error:
        if on_error:
            on_error(f"Refused image from {url}: {error}")
        return None
    return buffer
