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
    team.save_crest(buffer, "crest.png")

    response = admin_client.get(reverse("admin:soccertime_team_changelist"))

    assert response.status_code == 200
    assert b'width="48.0" height="24.0"' in response.content
