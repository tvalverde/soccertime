from django.db import migrations
from PIL import Image


def backfill(model, field_name):
    """Store the dimensions of every already uploaded image.

    Without this, `render_image` keeps opening and parsing each file to find out how big
    it is. Files that are missing or unreadable are skipped: the renderer falls back to
    the SVG placeholder for them, exactly as it did before.

    Rows are read with `values_list` and written with `update` so no model instance is
    ever built. Instantiating them would fire `post_init`, and at this point in the
    migration history the image field still declares `width_field`, whose handler reads
    the file and raises `FileNotFoundError` for the very rows this skips.
    """
    width_field, height_field = f"{field_name}_width", f"{field_name}_height"
    storage = model._meta.get_field(field_name).storage

    rows = model.objects.exclude(**{field_name: ""}).filter(**{f"{width_field}__isnull": True})

    for pk, name in rows.values_list("pk", field_name):
        if not name or not storage.exists(name):
            continue
        try:
            with storage.open(name) as handle, Image.open(handle) as image:
                width, height = image.size
        except (OSError, ValueError):
            continue
        model.objects.filter(pk=pk).update(**{width_field: width, height_field: height})


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
