from django.db import migrations, models

import soccertime.models


def dedupe_links(apps, schema_editor):
    """Merge links sharing the same URL so the unique constraint can be applied.

    Duplicates predate migration 0029, when uniqueness was scoped to (link, source)
    and the same URL could therefore exist once per source. The oldest row survives
    and inherits the sources and channels of the rows it absorbs.
    """
    ChannelLink = apps.get_model("soccertime", "ChannelLink")

    ChannelLink.objects.filter(link="").update(link=None)

    duplicated_urls = (
        ChannelLink.objects.exclude(link__isnull=True)
        .values("link")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .values_list("link", flat=True)
    )

    for url in list(duplicated_urls):
        survivor, *duplicates = ChannelLink.objects.filter(link=url).order_by("id")
        for duplicate in duplicates:
            survivor.sources.add(*duplicate.sources.all())
            survivor.channels.add(*duplicate.channels.all())
            survivor.verified = survivor.verified or duplicate.verified
        survivor.save(update_fields=["verified"])
        ChannelLink.objects.filter(pk__in=[duplicate.pk for duplicate in duplicates]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0032_alter_channellink_link"),
    ]

    operations = [
        migrations.RunPython(dedupe_links, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="channellink",
            name="link",
            field=models.CharField(
                blank=True,
                max_length=1000,
                null=True,
                unique=True,
                validators=[soccertime.models.validate_channel_link],
            ),
        ),
    ]
