# Migration to make event_type non-nullable after data migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('soccertime', '0026_populate_event_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='event_type',
            field=models.CharField(
                choices=[('match', 'Match'), ('race', 'Race'), ('simple', 'Simple Event')],
                db_index=True,
                editable=False,
                max_length=10,
            ),
        ),
    ]
