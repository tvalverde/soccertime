# Data migration to populate event_type for existing records

from django.db import migrations


def populate_event_type(apps, schema_editor):
    """Populate event_type field based on existing child tables."""
    Event = apps.get_model("soccertime", "Event")
    Match = apps.get_model("soccertime", "Match")
    Race = apps.get_model("soccertime", "Race")
    SimpleEvent = apps.get_model("soccertime", "SimpleEvent")

    # Get IDs for each type
    match_ids = Match.objects.values_list("event_ptr_id", flat=True)
    race_ids = Race.objects.values_list("event_ptr_id", flat=True)
    simple_ids = SimpleEvent.objects.values_list("event_ptr_id", flat=True)

    # Update in bulk
    Event.objects.filter(id__in=match_ids).update(event_type="match")
    Event.objects.filter(id__in=race_ids).update(event_type="race")
    Event.objects.filter(id__in=simple_ids).update(event_type="simple")


def reverse_populate_event_type(apps, schema_editor):
    """Reverse migration - set all event_type to null."""
    Event = apps.get_model("soccertime", "Event")
    Event.objects.all().update(event_type=None)


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0025_event_event_type"),
    ]

    operations = [
        migrations.RunPython(populate_event_type, reverse_populate_event_type),
    ]
