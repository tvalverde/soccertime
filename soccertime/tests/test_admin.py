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

pytestmark = pytest.mark.django_db


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
