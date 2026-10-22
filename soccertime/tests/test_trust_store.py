"""The certificate bundle the scrapers trust no longer trusts emSign ECC Root CA - G3.

Every outbound request the site makes goes through `requests`, which verifies TLS against
certifi's bundle rather than the system's. In October 2026 the private keys behind
eMudhra's emSign intermediates were found to be trivially weak, and certifi 2026.10.19
dropped the root they chain to. An older certifi keeps trusting it whatever the base image
does, so anyone holding one of those keys could impersonate any site the scrapers read.

The root is identified by the SHA-256 of its DER encoding, not by its label: the label is
a comment in certifi's file and absent from system bundles, and a check that reads it
would pass on any bundle that simply stopped writing comments.
"""

import hashlib
import re
import ssl
from pathlib import Path

import certifi

COMPROMISED_ROOT_SHA256 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"

PEM_CERTIFICATE = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


def trusted_fingerprints(bundle: Path) -> set[str]:
    return {
        hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() for pem in PEM_CERTIFICATE.findall(bundle.read_text())
    }


def test_the_bundle_is_readable():
    """Guards the assertion below: a parser reading nothing would trust nothing."""
    assert len(trusted_fingerprints(Path(certifi.where()))) > 100


def test_the_compromised_emsign_root_is_not_trusted():
    assert COMPROMISED_ROOT_SHA256 not in trusted_fingerprints(Path(certifi.where()))
