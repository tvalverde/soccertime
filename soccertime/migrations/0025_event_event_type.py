# Generated migration for adding event_type field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('soccertime', '0024_alter_competition_name_alter_event_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='event_type',
            field=models.CharField(
                choices=[('match', 'Match'), ('race', 'Race'), ('simple', 'Simple Event')],
                db_index=True,
                editable=False,
                max_length=10,
                null=True,
            ),
        ),
    ]
