from django.db import migrations


def forwards(apps, schema_editor):
    ChannelLink = apps.get_model("soccertime", "ChannelLink")

    for link in ChannelLink.objects.exclude(channel__isnull=True):
        link.channel.links.add(link)


def backwards(apps, schema_editor):
    ChannelLink = apps.get_model("soccertime", "ChannelLink")

    for link in ChannelLink.objects.all():
        channels = link.channels.all()
        if channels.exists():
            link.channel = channels.first()
            link.save()


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0015_channel_links"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
