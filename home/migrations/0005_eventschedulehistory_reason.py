from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0004_event_rescheduled_and_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventschedulehistory",
            name="reason",
            field=models.TextField(blank=True, default=""),
        ),
    ]
