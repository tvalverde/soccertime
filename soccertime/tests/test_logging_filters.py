"""What the access log keeps, and what it stops repeating.

Traefik probes `/healthz/` every second so a deploy can hand over between containers without
dropping requests, and the container health check adds one every thirty. Measured on
production that came to 89,280 lines a day — **97% of the access log** — against a json-file
driver that rotates at 10 MB × 3, so a genuine error left `docker logs` far sooner than it
should and `make remote-error-check` scanned mostly probe traffic.

The filter is conditional on purpose, which is the half worth testing: a probe that starts
failing is exactly what someone reading this log needs to see. The site has gone down twice
with the container reporting healthy, so a silent health check is not an option.
"""

import logging
import logging.config

import pytest

from soccertime.apps import attach_health_check_filter
from soccertime.logging_filters import SkipSuccessfulHealthChecks


def access_record(path, status, method="GET"):
    """An access line in uvicorn's own shape: '%s - "%s %s HTTP/%s" %d'."""
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", method, path, "1.1", status),
        exc_info=None,
    )


@pytest.fixture
def skip_health():
    return SkipSuccessfulHealthChecks()


class TestTheNoiseGoes:
    @pytest.mark.parametrize(
        "path",
        [
            # What production actually logs. uvicorn runs with `--root-path /soccertime` and
            # includes it in `scope["path"]`, so even the container probing
            # `http://localhost:8000/healthz/` is recorded with the prefix. An earlier
            # version of this filter anchored at the start of the path, matched nothing in
            # production, and every unit test here still passed — these cases exist so that
            # cannot happen twice.
            "/soccertime/healthz/",
            "/healthz/",
        ],
    )
    def test_a_passing_probe_is_dropped(self, skip_health, path):
        assert skip_health.filter(access_record(path, 200)) is False

    def test_a_probe_with_a_query_string_is_dropped_too(self, skip_health):
        """uvicorn logs the path with its query string attached."""
        assert skip_health.filter(access_record("/soccertime/healthz/?probe=1", 200)) is False


class TestTheEvidenceStays:
    @pytest.mark.parametrize("status", [500, 502, 503, 404, 301])
    def test_a_failing_probe_is_always_logged(self, skip_health, status):
        """The reason this filter is conditional rather than a path match.

        A health check answering 500 while the container still reports healthy is how this
        site went down before; silencing it would remove the only trace.
        """
        assert skip_health.filter(access_record("/soccertime/healthz/", status)) is True

    def test_a_real_request_is_untouched(self, skip_health):
        assert skip_health.filter(access_record("/soccertime/agenda/", 200)) is True

    def test_a_path_merely_starting_similarly_is_untouched(self, skip_health):
        assert skip_health.filter(access_record("/soccertime/healthz-report/", 200)) is True


class TestItRefusesToGuess:
    """Anything that is not the access line this filter knows about passes through.

    uvicorn could change its format, and another logger could be attached to the same
    handler. Letting an unrecognised record through is the safe direction: the cost is a
    line of noise, where the opposite is losing something nobody knew was being dropped.
    """

    def test_a_record_with_no_args_passes(self, skip_health):
        record = access_record("/healthz/", 200)
        record.args = None

        assert skip_health.filter(record) is True

    def test_a_record_of_another_shape_passes(self, skip_health):
        record = access_record("/healthz/", 200)
        record.args = ("something", "else")

        assert skip_health.filter(record) is True

    def test_a_non_numeric_status_passes(self, skip_health):
        record = access_record("/healthz/", 200)
        record.args = ("127.0.0.1", "GET", "/healthz/", "1.1", "200")

        assert skip_health.filter(record) is True


class TestItAttachesWithoutSilencingTheLog:
    """Attaching the filter must not cost uvicorn its handler.

    The first attempt declared this in Django's `LOGGING` setting. `dictConfig` does not
    merge — naming a logger resets every key left unspecified — so supplying only `filters`
    cleared uvicorn's handler and the access log went **completely silent**, real requests
    included. The unit tests passed anyway because they attached their own handler; only
    running it against the real stack showed it. These assert the shape that broke.
    """

    @pytest.fixture
    def uvicorn_logging(self):
        """The logging state uvicorn leaves behind when it boots, restored afterwards."""
        from uvicorn.config import LOGGING_CONFIG

        logger = logging.getLogger("uvicorn.access")
        before = (list(logger.handlers), list(logger.filters), logger.propagate, logger.level)
        logging.config.dictConfig(LOGGING_CONFIG)
        yield logger
        logger.handlers, logger.filters, logger.propagate, logger.level = (
            before[0],
            before[1],
            before[2],
            before[3],
        )

    def test_the_access_handler_survives(self, uvicorn_logging):
        assert uvicorn_logging.handlers, "uvicorn had no handler to begin with"

        attach_health_check_filter()

        assert uvicorn_logging.handlers, "attaching the filter silenced the access log"

    def test_the_filter_is_actually_attached(self, uvicorn_logging):
        attach_health_check_filter()

        assert any(isinstance(f, SkipSuccessfulHealthChecks) for f in uvicorn_logging.filters)

    def test_attaching_twice_does_not_stack_filters(self, uvicorn_logging):
        """`ready()` can run more than once in a process; the filter is not cumulative."""
        attach_health_check_filter()
        attach_health_check_filter()

        attached = [f for f in uvicorn_logging.filters if isinstance(f, SkipSuccessfulHealthChecks)]
        assert len(attached) == 1
