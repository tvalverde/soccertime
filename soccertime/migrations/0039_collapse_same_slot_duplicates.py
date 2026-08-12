"""Remove the duplicate rows the old event identity accumulated.

`details` — the phase text, which the source rephrases freely — used to be part of a race's
and a simple event's identity, so every rephrasing created a second row in the same slot:
234 rows sharing (competition, name, date) with another existed in production when this was
found, and they render as visibly duplicated listings. The identity no longer includes the
text, and the scraper's reconciliation heals a slot the moment a scrape covers it — but a
slot the pages no longer cover would keep its twins forever, so they are collapsed here
once. The freshest row wins, matching what `upsert_event` does when it meets a twin.

Read with `values_list`, delete by pk: no model instance is ever built, per the project
rule about data migrations and historical models.
"""

from django.db import migrations


def collapse(apps, schema_editor):
    for model_name in ("Race", "SimpleEvent"):
        model = apps.get_model("soccertime", model_name)
        newest_per_slot: dict[tuple, tuple] = {}
        doomed: list[int] = []
        rows = model.objects.values_list("pk", "competition_id", "name", "date", "last_updated_at")
        for pk, competition_id, name, date, updated in rows:
            slot = (competition_id, name, date)
            kept = newest_per_slot.get(slot)
            if kept is None:
                newest_per_slot[slot] = (updated, pk)
            elif updated > kept[0]:
                doomed.append(kept[1])
                newest_per_slot[slot] = (updated, pk)
            else:
                doomed.append(pk)
        if doomed:
            model.objects.filter(pk__in=doomed).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0038_event_presence_bookkeeping"),
    ]

    operations = [
        migrations.RunPython(collapse, migrations.RunPython.noop),
    ]
