"""What the image has to be, now that it is built once and shipped rather than rebuilt.

Production used to build its own image from a `git archive` of the commit being deployed,
so the base image was resolved on the server, at deploy time, from the floating
`python:3-alpine` tag. That is how the interpreter under the site could change without a
single line of this repository changing with it — and why the rollback image is kept: a
rebuild of the same commit is not the same image.

An explicit minor version is what makes the build reproducible and what lets the rest of
the tooling agree with it: `test_ci_workflow.py` reads this number so the suite runs on the
interpreter production runs, rather than on whatever the runner defaults to.

Read from the Dockerfile for the same reason `test_image_defaults.py` does: the question is
what the built image is, and no amount of reading Python can answer it.
"""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def base_image() -> str | None:
    match = re.search(r"(?m)^FROM\s+(\S+)", DOCKERFILE.read_text())
    return match.group(1) if match else None


def base_image_python_version() -> str | None:
    """The `3.14` of `python:3.14-alpine`, or None while the tag is still floating."""
    match = re.fullmatch(r"python:(\d+\.\d+)-alpine", base_image() or "")
    return match.group(1) if match else None


def test_the_dockerfile_declares_a_base_image():
    """Guards the assertion below: a regex matching nothing would assert nothing."""
    assert base_image()


def test_the_interpreter_is_pinned_to_a_minor_version():
    """`python:3-alpine` resolves afresh on every build, on whichever machine builds it."""
    assert base_image_python_version(), f"{base_image()} does not pin a minor version"
