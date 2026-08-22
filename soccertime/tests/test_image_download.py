"""Every URL reaching `download_image` came out of scraped HTML, so it is hostile input.

The fetch used to accept anything: any scheme, any address, any size, any content. It read
`response.content`, which pulls a whole body into memory however long it is, inside a
container limited to 512 MB, and it followed redirects without looking at where they led —
from a container sharing a network with Traefik and the rest of the services on the host.

These tests are grouped by the guard they exercise, in the order the guards run.
"""

import io
import socket
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from soccertime.management.commands._image_download import (
    MAX_IMAGE_BYTES,
    MAX_REDIRECTS,
    download_image,
)

from .conftest import image_response


def image_bytes(size=(32, 24), image_format="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format=image_format)
    return buffer.getvalue()


def response_for(body=b"", **kwargs):
    return image_response(body, **kwargs)


def resolving_to(monkeypatch, address):
    monkeypatch.setattr(
        "soccertime.management.commands._image_download.socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", (address, 0))],
    )


class TestTheScheme:
    @pytest.mark.parametrize(
        "url",
        ["file:///etc/passwd", "ftp://example.com/flag.png", "javascript:alert(1)", "gopher://example.com/"],
    )
    def test_only_http_and_https_are_fetched(self, url):
        errors = []

        assert download_image(url, on_error=errors.append) is None
        assert any("disallowed scheme" in error for error in errors)

    def test_a_missing_url_is_still_tolerated(self):
        """Both callers pass an optional URL straight through."""
        assert download_image(None) is None
        assert download_image("") is None


class TestTheDestination:
    """The container sits on the same network as Traefik and the other services."""

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",  # the container itself
            "10.0.0.5",  # the docker network
            "172.18.0.2",  # nassut-net
            "192.168.1.1",  # the host's LAN
            "169.254.169.254",  # cloud metadata
            "::1",
        ],
    )
    def test_a_url_resolving_inside_the_deployment_is_refused(self, monkeypatch, address):
        resolving_to(monkeypatch, address)
        errors = []

        assert download_image("https://evil.example/flag.png", on_error=errors.append) is None
        assert any("non-public address" in error for error in errors)

    def test_every_resolved_address_is_checked_not_only_the_first(self, monkeypatch):
        """A host answering with a public and a private record must not pass on the public one."""
        monkeypatch.setattr(
            "soccertime.management.commands._image_download.socket.getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("10.0.0.5", 0))],
        )
        errors = []

        assert download_image("https://evil.example/flag.png", on_error=errors.append) is None
        assert any("non-public address" in error for error in errors)

    @pytest.mark.parametrize(
        "failure",
        [
            socket.gaierror("no such host"),
            # An over-long label makes the IDNA encoder raise this instead, and these
            # hostnames come from scraped HTML where a malformed one is unremarkable.
            UnicodeError("label too long"),
            OSError("network unreachable"),
        ],
    )
    def test_a_name_that_does_not_resolve_is_reported_not_raised(self, monkeypatch, failure):
        monkeypatch.setattr(
            "soccertime.management.commands._image_download.socket.getaddrinfo",
            Mock(side_effect=failure),
        )
        errors = []

        assert download_image("https://nowhere.example/flag.png", on_error=errors.append) is None
        assert any("could not resolve" in error for error in errors)


class TestRedirects:
    """Letting requests follow them is what would undo the address check."""

    def test_a_redirect_into_the_private_network_is_refused(self, monkeypatch):
        addresses = iter(["93.184.216.34", "169.254.169.254"])
        monkeypatch.setattr(
            "soccertime.management.commands._image_download.socket.getaddrinfo",
            lambda host, port: [(2, 1, 6, "", (next(addresses), 0))],
        )
        redirect = response_for(status=302, is_redirect=True, headers={"Location": "http://metadata.example/"})
        errors = []

        with patch("requests.get", return_value=redirect):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("non-public address" in error for error in errors)

    def test_a_redirect_to_another_scheme_is_refused(self, public_dns):
        redirect = response_for(status=302, is_redirect=True, headers={"Location": "file:///etc/passwd"})
        errors = []

        with patch("requests.get", return_value=redirect):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("disallowed scheme" in error for error in errors)

    def test_a_redirect_loop_gives_up(self, public_dns):
        redirect = response_for(status=302, is_redirect=True, headers={"Location": "https://public.example/again"})
        errors = []

        with patch("requests.get", return_value=redirect) as get:
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert get.call_count == MAX_REDIRECTS + 1
        assert any("redirects" in error for error in errors)

    def test_a_redirect_to_a_public_address_is_followed(self, public_dns):
        redirect = response_for(status=302, is_redirect=True, headers={"Location": "https://cdn.example/flag.png"})
        final = response_for(body=image_bytes())
        errors = []

        with patch("requests.get", side_effect=[redirect, final]):
            result = download_image("https://public.example/flag.png", on_error=errors.append)

        assert result is not None
        assert not errors


class TestTheConnectionIsPinnedToTheVettedAddress:
    """The check resolves the name, then `requests` resolves it again to connect.

    Nothing forced the two lookups to agree, so a hostile DNS with a short TTL could answer
    public to the check and internal to the fetch — a rebinding bypass of the whole
    destination guard. The fix resolves once, vets, and connects only to that address: the
    name is never resolved a second time.
    """

    def _record_pinned_target(self, monkeypatch):
        """Capture the (host, port) every connection is actually opened to.

        `create_connection` is urllib3's single choke point for opening a socket. The pin
        rewrites the address it is handed; recording that address is how a test sees where
        the fetch would really have gone, without a real network.
        """
        opened = []

        def fake_create_connection(address, *args, **kwargs):
            opened.append(address)
            raise OSError("no real socket in tests")

        monkeypatch.setattr(
            "urllib3.util.connection.create_connection",
            fake_create_connection,
        )
        return opened

    def test_the_socket_is_opened_to_the_vetted_ip_not_a_second_lookup(self, monkeypatch):
        """The rebinding case, which the pre-fix code failed.

        The vet sees a public address and passes. When the connection is opened it must go
        to that same address — never to whatever a second resolution of the name returns.
        """
        monkeypatch.setattr(
            "soccertime.management.commands._image_download.socket.getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        opened = self._record_pinned_target(monkeypatch)

        download_image("https://evil.example/flag.png", on_error=lambda _: None)

        assert opened, "no connection was attempted"
        assert all(host == "93.184.216.34" for host, _ in opened), opened

    def test_the_original_hostname_still_reaches_requests_for_sni(self, monkeypatch):
        """Pinning the socket must not strip the name TLS needs.

        The URL requests is given keeps its hostname, so the Host header and the TLS SNI are
        the name, not the IP — otherwise certificate validation for a name-based host breaks.
        """
        resolving_to(monkeypatch, "93.184.216.34")
        self._record_pinned_target(monkeypatch)

        with patch("requests.get", side_effect=AssertionError("stop before the socket")) as get:
            try:
                download_image("https://cdn.example/flag.png", on_error=lambda _: None)
            except AssertionError:
                pass

        assert get.call_args is not None
        url = get.call_args.args[0] if get.call_args.args else get.call_args.kwargs["url"]
        assert "cdn.example" in url

    def test_a_redirect_hop_is_pinned_to_its_own_host(self, monkeypatch):
        """Each hop resolves, vets and pins independently — the pin is not stuck on hop one."""
        seen_hosts = []

        def getaddrinfo(host, port):
            seen_hosts.append(host)
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr("soccertime.management.commands._image_download.socket.getaddrinfo", getaddrinfo)
        redirect = response_for(status=302, is_redirect=True, headers={"Location": "https://cdn.example/flag.png"})
        final = response_for(body=image_bytes())

        with patch("requests.get", side_effect=[redirect, final]):
            download_image("https://public.example/flag.png", on_error=lambda _: None)

        assert "public.example" in seen_hosts
        assert "cdn.example" in seen_hosts

    def test_a_vetted_ipv6_address_is_pinned_too(self, monkeypatch):
        """`getaddrinfo` can hand back v6; the vet and the pin must both cope."""
        monkeypatch.setattr(
            "soccertime.management.commands._image_download.socket.getaddrinfo",
            lambda host, port: [(10, 1, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0))],
        )
        opened = self._record_pinned_target(monkeypatch)

        download_image("https://v6.example/flag.png", on_error=lambda _: None)

        assert opened, "no connection was attempted"
        assert all(host == "2606:2800:220:1:248:1893:25c8:1946" for host, _ in opened), opened


class TestTheSize:
    def test_a_declared_length_over_the_cap_is_refused_before_reading(self, public_dns):
        response = response_for(headers={"Content-Length": str(MAX_IMAGE_BYTES + 1)})
        errors = []

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        response.iter_content.assert_not_called()
        assert any("over the" in error for error in errors)

    def test_a_body_over_the_cap_is_abandoned_partway(self, public_dns):
        """The point is that reading stops, not merely that the result is None."""
        chunks_read = 0

        def endless(size):
            nonlocal chunks_read
            while True:
                chunks_read += 1
                yield b"x" * size

        response = response_for()
        response.iter_content = endless
        errors = []

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert chunks_read < MAX_IMAGE_BYTES  # it stopped instead of running forever
        assert any("exceeds" in error for error in errors)


class TestTheContent:
    def test_a_non_image_content_type_is_refused(self, public_dns):
        response = response_for(body=b"<html></html>", content_type="text/html")
        errors = []

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("text/html" in error for error in errors)

    def test_content_that_is_not_an_image_is_refused_however_the_url_ends(self, public_dns):
        """The URL said `.png` and the server said `image/png`. Neither is evidence."""
        response = response_for(body=b"<svg onload=alert(1)></svg>")
        errors = []

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("not a decodable image" in error for error in errors)

    def test_a_format_outside_the_allowlist_is_refused(self, public_dns):
        response = response_for(body=image_bytes(image_format="BMP"))
        errors = []

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("does not store" in error for error in errors)

    @pytest.mark.parametrize("image_format", ["PNG", "WEBP", "GIF"])
    def test_the_formats_this_site_stores_are_accepted(self, public_dns, image_format):
        body = image_bytes(image_format=image_format)
        response = response_for(body=body)

        with patch("requests.get", return_value=response):
            result = download_image("https://public.example/flag.png")

        assert result is not None
        assert result.getvalue() == body

    def test_a_non_200_returns_nothing(self, public_dns):
        response = response_for(status=404)

        with patch("requests.get", return_value=response):
            assert download_image("https://public.example/flag.png") is None


class TestFailuresAreReportedNotRaised:
    """One unreachable image must never abort a scraping run."""

    def test_a_network_error_is_reported(self, public_dns):
        errors = []

        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            assert download_image("https://public.example/flag.png", on_error=errors.append) is None

        assert any("Could not download" in error for error in errors)

    def test_nothing_raises_when_no_handler_is_given(self, public_dns):
        with patch("requests.get", side_effect=requests.Timeout("slow")):
            assert download_image("https://public.example/flag.png") is None
