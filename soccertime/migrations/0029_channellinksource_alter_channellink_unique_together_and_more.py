from django.db import migrations, models
from django.db.models import Q


def forwards(apps, schema_editor):
    ChannelLink = apps.get_model("soccertime", "ChannelLink")
    ChannelLinkSource = apps.get_model("soccertime", "ChannelLinkSource")

    # Crear sources únicos por nombre
    existing_sources = (
        ChannelLink.objects.exclude(Q(source__isnull=True) | Q(source="")).values_list("source", flat=True).distinct()
    )
    name_to_source = {}
    for name in existing_sources:
        src, _ = ChannelLinkSource.objects.get_or_create(name=name, defaults={"display_name": name})
        name_to_source[name] = src

    # Asignar M2M y limpiar campo legacy
    for link in ChannelLink.objects.all():
        if not link.source:
            continue
        src = name_to_source.get(link.source)
        if src:
            link.sources.add(src)


def backwards(apps, schema_editor):
    ChannelLink = apps.get_model("soccertime", "ChannelLink")
    ChannelLinkSource = apps.get_model("soccertime", "ChannelLinkSource")

    # Restaurar el campo source con el primer source asociado (si existe)
    for link in ChannelLink.objects.all():
        first_source = link.sources.first()
        if first_source:
            link.source = first_source.name
            link.save(update_fields=["source"])

    ChannelLinkSource.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("soccertime", "0028_favorite_favorite_requires_competition_or_team"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChannelLinkSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("display_name", models.CharField(blank=True, max_length=255, null=True)),
                ("enabled", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="channellink",
            name="sources",
            field=models.ManyToManyField(blank=True, related_name="links", to="soccertime.channellinksource"),
        ),
        migrations.AlterUniqueTogether(
            name="channellink",
            unique_together=set(),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="channellink",
            name="source",
        ),
    ]
