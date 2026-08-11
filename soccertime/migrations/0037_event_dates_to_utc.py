"""Store event times as real UTC instead of Spanish wall clock wearing a UTC label.

The scraper called `make_aware(value, get_current_timezone())` with `TIME_ZONE = "UTC"`, so no
offset was ever applied: a 22:00 kick-off was stored as `22:00 UTC`. Rendering in UTC printed
it back unchanged, which is why the site looked right while every comparison against
`timezone.now()` was out by the offset — the front page held 111 events with 7 of them already
finished, because a window declaring three hours retained five.

This runs together with `TIME_ZONE = "Europe/Madrid"` and the scraper change, and the display
does not move: the two halves cancel exactly. It must not run without them.

The conversion lives in `soccertime.event_dates` so it can be tested against both seasons.
Importing it rather than copying it here is deliberate and safe: it touches no model fields,
only `pk` and `date`, both of which exist in every version of this table.
"""

from django.db import migrations

from soccertime.event_dates import convert_stored_dates


def to_utc(apps, schema_editor):
    convert_stored_dates(apps.get_model("soccertime", "Event"), to_utc=True)


def to_wall_clock(apps, schema_editor):
    convert_stored_dates(apps.get_model("soccertime", "Event"), to_utc=False)


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0036_alter_flag_image_alter_team_crest"),
    ]

    operations = [
        migrations.RunPython(to_utc, to_wall_clock),
    ]
