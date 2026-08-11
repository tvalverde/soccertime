"""What the image is configured to do when nothing tells it otherwise.

The Dockerfile used to bake `DJANGO_DEBUG=true` and `DJANGO_ADMIN_ENABLED=true`, so
production was safe only for as long as `.env.production` kept overriding them — a file
deliberately kept out of the repository, and therefore one that can lose a line without
anything noticing. Drop the debug entry and the container comes up serving stack traces and
settings to any visitor; drop the key as well and it falls back to the hardcoded development
one, which makes forging a session trivial.

Reading a Dockerfile from a test is unusual, and it is the only thing that pins this. Every
other test in the suite runs with `.env` loaded, so all of them would go on passing if the
image quietly went back to defaulting to debug.
"""

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"

# What each variable has to be when nothing overrides it. `DJANGO_USE_X_FORWARDED_HOST` is
# here because trusting a header the client can set is only ever right behind a proxy that
# overwrites it, which the image cannot know it is behind.
SAFE_DEFAULTS = {
    "DJANGO_DEBUG": "false",
    "DJANGO_ADMIN_ENABLED": "false",
    "DJANGO_USE_X_FORWARDED_HOST": "false",
}


def baked_environment():
    """The variables the image sets, from its `ENV` instructions.

    Parsed rather than imported: the point is what the built image carries, which no amount
    of reading `settings.py` can tell us.
    """
    text = DOCKERFILE.read_text()
    # Line continuations first, so a multi-line ENV reads as one instruction.
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    variables = {}
    for line in joined.splitlines():
        if not line.startswith("ENV "):
            continue
        for assignment in re.findall(r"(\w+)=(\S+)", line[4:]):
            variables[assignment[0]] = assignment[1]
    return variables


@pytest.mark.parametrize(("variable", "expected"), sorted(SAFE_DEFAULTS.items()))
def test_the_image_defaults_to_the_safe_value(variable, expected):
    assert baked_environment().get(variable) == expected


def test_no_secret_key_is_baked_in():
    """A key in the image is a key in every layer that ever held it, and in every copy."""
    assert "DJANGO_SECRET_KEY" not in baked_environment()


def test_the_parser_reads_the_multi_line_env_block():
    """Guards the test itself: a parser that silently found nothing would assert nothing."""
    variables = baked_environment()

    assert len(variables) > len(SAFE_DEFAULTS)
    assert variables["DJANGO_DATABASE_DEFAULT_NAME"] == "/code/db/db.sqlite3"
