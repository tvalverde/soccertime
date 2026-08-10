from django.db import migrations


def backfill(model, field_name):
    """Store the dimensions of every already uploaded image.

    Without this, `render_image` keeps opening and parsing each file to find out how big
    it is. Unreadable or missing files are skipped: the renderer falls back to reading
    them, exactly as it did before.
    """
    width_field, height_field = f"{field_name}_width", f"{field_name}_height"
    updated = []

    for instance in model.objects.exclude(**{f"{field_name}": ""}).filter(**{f"{width_field}__isnull": True}):
        image = getattr(instance, field_name)
        if not image:
            continue
        try:
            width, height = image.width, image.height
        except (OSError, ValueError):
            continue
        setattr(instance, width_field, width)
        setattr(instance, height_field, height)
        updated.append(instance)

    if updated:
        model.objects.bulk_update(updated, [width_field, height_field], batch_size=500)
    return len(updated)


def backfill_image_dimensions(apps, schema_editor):
    backfill(apps.get_model("soccertime", "Flag"), "image")
    backfill(apps.get_model("soccertime", "Team"), "crest")


def clear_image_dimensions(apps, schema_editor):
    apps.get_model("soccertime", "Flag").objects.update(image_width=None, image_height=None)
    apps.get_model("soccertime", "Team").objects.update(crest_width=None, crest_height=None)


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0034_alter_event_options_flag_image_height_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_image_dimensions, clear_image_dimensions),
    ]
