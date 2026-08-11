"""
Tests for soccertime admin.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from soccertime.models import Channel, Competition, Match

# The admin is only routed when `DJANGO_ADMIN_ENABLED` is true, and production runs with
# it off. Naming the URLconf here keeps these tests about the admin's behaviour rather
# than about which environment the suite happens to run in.
pytestmark = [pytest.mark.django_db, pytest.mark.urls("soccertime.tests.urls_with_admin")]


def test_match_admin_queries_performance(admin_client, db, sport, team_home, team_away):
    """Should have a constant number of queries regardless of the number of matches."""
    comp = Competition.objects.create(name="Admin Comp", sport=sport)

    # Create multiple matches with channels
    for i in range(5):
        match = Match.objects.create(
            date=timezone.now() + datetime.timedelta(days=1),
            competition=comp,
            local=team_home,
            visitor=team_away,
        )
        channel = Channel.objects.create(name=f"Channel {i}")
        match.channels.add(channel)

    with CaptureQueriesContext(connection) as queries:
        response = admin_client.get(reverse("admin:soccertime_match_changelist"))

    assert response.status_code == 200
    # With optimization, this should be low (no N+1 per match).
    # Since there are some auth and session queries as well, less than 20 is safe.
    assert len(queries) < 35


@pytest.mark.parametrize(
    "model_name",
    ["team", "flag", "competition", "favorite"],
)
def test_changelists_that_render_images(admin_client, db, model_name, team_home, flag, competition):
    """These list pages call the shared renderer; a broken import breaks the admin."""
    from soccertime.models import Favorite

    Favorite.objects.create(team=team_home, order=1)

    response = admin_client.get(reverse(f"admin:soccertime_{model_name}_changelist"))

    assert response.status_code == 200
    assert b"bi-emoji-dizzy" in response.content, "rows without an image show the placeholder"


def test_changelist_renders_a_stored_image(admin_client, db, settings, tmp_path):
    """The <img> path, not just the placeholder."""
    import io

    from PIL import Image

    from soccertime.models import Team

    settings.MEDIA_ROOT = tmp_path
    team = Team.objects.create(name="Con escudo")
    buffer = io.BytesIO()
    Image.new("RGB", (48, 24)).save(buffer, format="PNG")
    team.save_crest(buffer)

    response = admin_client.get(reverse("admin:soccertime_team_changelist"))

    assert response.status_code == 200
    assert b'width="48.0" height="24.0"' in response.content


def test_the_sortable_admin_has_a_script_for_this_django():
    """`django-admin-sortable2` ships one patched `actions.js` per Django version.

    It swaps the admin's own file for its copy, named after the running Django:

        js[js.index('admin/js/actions.js')] = f'adminsortable2/js/actions-{MAJOR}.{MINOR}.js'

    So a Django upgrade the package has not caught up with leaves the sortable changelists
    asking for a file nobody shipped. Under `ManifestStaticFilesStorage` — which is what
    production uses — a missing static file raises rather than 404s, so `Sport` and
    `Favorite` answer 500 while every other admin page is fine.

    Nothing else here would notice. The suite runs with `DEBUG=true`, where `{% static %}`
    validates nothing; `collectstatic` succeeds, since the file is simply absent rather than
    broken; and the smoke test never opens the admin, which production keeps switched off
    anyway. The failure would surface on the next `make remote-admin-on`, long after the
    deploy that caused it.

    Measured on Django 6.1: `/admin/soccertime/sport/` and `/admin/soccertime/favorite/`
    both 500, `/admin/soccertime/team/` — which is not sortable — stays at 200. That is why
    this project is still on 6.0.8, and this test is what will say when it need not be.
    """
    from django import VERSION
    from django.contrib.staticfiles import finders

    expected = f"adminsortable2/js/actions-{VERSION[0]}.{VERSION[1]}.js"

    assert finders.find(expected), (
        f"django-admin-sortable2 ships no {expected}, so the sortable changelists will "
        f"raise under manifest storage. Check for a release that supports Django "
        f"{VERSION[0]}.{VERSION[1]} before upgrading."
    )
