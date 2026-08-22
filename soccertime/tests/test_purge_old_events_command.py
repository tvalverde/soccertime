import datetime
import io

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from soccertime.models import Event, Match, Race, SimpleEvent


@pytest.mark.django_db
class TestPurgeOldEventsCommand:
    def test_dry_run_does_not_delete_events(self, db, competition, team_home, team_away):
        now = timezone.now()
        old_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=now - datetime.timedelta(days=120),
        )
        recent_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=now + datetime.timedelta(days=1),
        )

        out = io.StringIO()
        call_command("purge_old_events", days=90, dry_run=True, stdout=out)
        output = out.getvalue()

        assert "[DRY RUN]" in output
        assert "Would delete 1 historical events" in output
        assert Event.objects.filter(pk=old_match.pk).exists()
        assert Event.objects.filter(pk=recent_match.pk).exists()

    def test_purge_deletes_old_events_and_preserves_recent(
        self, db, competition, competition_tour, competition_roland_garros, team_home, team_away
    ):
        now = timezone.now()
        # Old events (>90 days)
        old_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=now - datetime.timedelta(days=100),
        )
        old_race = Race.objects.create(
            competition=competition_tour,
            name="Etapa Antigua",
            date=now - datetime.timedelta(days=150),
        )
        old_simple = SimpleEvent.objects.create(
            competition=competition_roland_garros,
            name="Partido Antiguo",
            date=now - datetime.timedelta(days=95),
        )

        # Recent and future events (<90 days)
        recent_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=now - datetime.timedelta(days=30),
        )
        future_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=now + datetime.timedelta(days=2),
        )

        out = io.StringIO()
        call_command("purge_old_events", days=90, stdout=out)
        output = out.getvalue()

        assert "Successfully purged" in output

        # Assert old events and child records are deleted
        assert not Event.objects.filter(pk=old_match.pk).exists()
        assert not Match.objects.filter(pk=old_match.pk).exists()
        assert not Event.objects.filter(pk=old_race.pk).exists()
        assert not Race.objects.filter(pk=old_race.pk).exists()
        assert not Event.objects.filter(pk=old_simple.pk).exists()
        assert not SimpleEvent.objects.filter(pk=old_simple.pk).exists()

        # Assert recent and future events remain
        assert Event.objects.filter(pk=recent_match.pk).exists()
        assert Event.objects.filter(pk=future_match.pk).exists()

    def test_custom_before_date(self, db, competition, team_home, team_away):
        old_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.make_aware(datetime.datetime(2025, 6, 1, 12, 0)),
        )
        newer_match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.make_aware(datetime.datetime(2026, 6, 1, 12, 0)),
        )

        out = io.StringIO()
        call_command("purge_old_events", before_date="2026-01-01", stdout=out)

        assert not Event.objects.filter(pk=old_match.pk).exists()
        assert Event.objects.filter(pk=newer_match.pk).exists()

    def test_no_events_matching_criteria(self, db):
        out = io.StringIO()
        call_command("purge_old_events", days=90, stdout=out)
        output = out.getvalue()

        assert "No historical events match the purge criteria" in output

    def test_negative_days_raises_command_error(self, db):
        with pytest.raises(CommandError, match="positive integer"):
            call_command("purge_old_events", days=-5)

    def test_invalid_before_date_raises_command_error(self, db):
        with pytest.raises(CommandError, match="Invalid date format"):
            call_command("purge_old_events", before_date="invalid-date")
