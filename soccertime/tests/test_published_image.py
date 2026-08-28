"""What the image has to be, now that it is built once and shipped rather than rebuilt.

Production used to build its own image from a `git archive` of the commit being deployed,
so the base image was resolved on the server, at deploy time, from the floating
`python:3-alpine` tag. That is how the interpreter under the site could change without a
single line of this repository changing with it — and why the rollback image is kept: a
rebuild of the same commit is not the same image.

An explicit minor version is what makes the build reproducible and what lets the rest of
the tooling agree with it: `test_ci_workflow.py` reads this number so the suite runs on the
interpreter production runs, rather than on whatever the runner defaults to.

The build context matters for the same reason. `COPY . .` carries whatever the ignore file
does not stop, and until now nothing in this repository depended on that file being right:
the server built from `git archive HEAD`, which contains tracked files and nothing else. A
build from a working copy is a different thing entirely — 20 MB of database copies in `db/`,
53 MB of backups, and the private key under `.docker/traefik/certs/` all sit beside the
application and were all being copied in. The image is now built by CI and published to a
registry anyone can pull, so what the ignore file misses is not wasted space, it is
disclosure.

Docker's matching is reimplemented here rather than approximated with `fnmatch`, because the
difference is the whole point: `*` does not cross a `/`, so `*.sqlite3` never covered
`db/db.sqlite3` however much it looks like it should.

Read from the Dockerfile for the same reason `test_image_defaults.py` does: the question is
what the built image is, and no amount of reading Python can answer it.
"""

import re
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
MAKEFILE = ROOT / "Makefile"

# Paths that must never reach a published image. Named rather than discovered, because most
# of them exist only on a working machine: a fresh checkout has no `db/`, no `backups/` and
# no certificates, so a test that looked for them would pass in CI by finding nothing.
NEVER_SHIPPED = {
    "the production environment file, which holds the secret key": ".env.production",
    "the database and the copies kept beside it": "db/db.sqlite3.backup.20260812_180032",
    "the snapshots the deploy pulls down": "backups/db.20260810_203027.sqlite3.gz",
    "the local TLS private key": ".docker/traefik/certs/mojon.local.key",
    "per-machine assistant state": ".claude/settings.local.json",
    "editor state": ".idea/workspace.xml",
    "the external channel lists, which are not this project's data": "newera.txt",
}


def base_image() -> str | None:
    match = re.search(r"(?m)^FROM\s+(\S+)", DOCKERFILE.read_text())
    return match.group(1) if match else None


def base_image_python_version() -> str | None:
    """The `3.14` of `python:3.14-alpine`, or None while the tag is still floating."""
    match = re.fullmatch(r"python:(\d+\.\d+)-alpine", base_image() or "")
    return match.group(1) if match else None


def ignore_patterns() -> list[str]:
    return [line.strip() for line in DOCKERIGNORE.read_text().splitlines() if line.strip() and not line.startswith("#")]


def as_regex(pattern: str) -> re.Pattern[str]:
    """One `.dockerignore` pattern, with Docker's meaning of `*`: anything but a separator."""
    translated = ""
    for token in re.split(r"(\*\*|\*|\?)", pattern.rstrip("/")):
        translated += {"**": ".*", "*": "[^/]*", "?": "[^/]"}.get(token, re.escape(token))
    return re.compile(f"{translated}$")


def excluded(relative_path: str) -> bool:
    """Whether the build context would leave this path out.

    A pattern matching a directory takes its whole subtree with it, so every parent is
    offered to the pattern as well as the path itself.
    """
    candidates = [PurePosixPath(relative_path), *PurePosixPath(relative_path).parents]
    return any(
        as_regex(pattern).fullmatch(str(candidate))
        for pattern in ignore_patterns()
        for candidate in candidates
        if str(candidate) != "."
    )


def labels() -> dict[str, str]:
    """The `LABEL` instructions the image carries."""
    joined = re.sub(r"\\\s*\n\s*", " ", DOCKERFILE.read_text())
    return dict(re.findall(r'([\w.]+)="([^"]*)"', " ".join(re.findall(r"(?m)^LABEL\s+(.*)$", joined))))


def pruned_by_label() -> str | None:
    """The label filter the deploy prunes superseded images with, from the Makefile."""
    match = re.search(r"--filter label=([\w.]+)=(\S+)", MAKEFILE.read_text())
    return match.group(1) if match else None


def test_the_dockerfile_declares_a_base_image():
    """Guards the assertion below: a regex matching nothing would assert nothing."""
    assert base_image()


def test_the_interpreter_is_pinned_to_a_minor_version():
    """`python:3-alpine` resolves afresh on every build, on whichever machine builds it."""
    assert base_image_python_version(), f"{base_image()} does not pin a minor version"


class TestTheBuildContextCarriesTheApplicationAndNothingElse:
    def test_the_matcher_reads_the_patterns_both_ways(self):
        """Guards the assertions below: a matcher that always agreed would assert nothing."""
        assert excluded(".env.production")
        assert not excluded("manage.py")

    @pytest.mark.parametrize("path", sorted(NEVER_SHIPPED.values()), ids=lambda path: path)
    def test_it_is_left_out_of_the_image(self, path):
        assert excluded(path)


class TestTheImageSaysWhatItIs:
    def test_the_deploy_can_still_tell_this_project_images_apart(self):
        """The prune filter is the contract: without this label it would match nothing, and
        superseded images would accumulate on a host whose other services build their own."""
        assert pruned_by_label() == "org.opencontainers.image.title"
        assert labels().get(pruned_by_label()) == "soccertime"

    def test_the_package_names_the_repository_it_came_from(self):
        """What links the published package to this repository, and with it the provenance
        of an image the deploy pulls without ever looking at the code inside."""
        assert labels().get("org.opencontainers.image.source") == "https://github.com/tvalverde/soccertime"
