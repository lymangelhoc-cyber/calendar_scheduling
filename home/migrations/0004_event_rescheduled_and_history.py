from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0003_event_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rescheduled", "Rescheduled"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="EventScheduleHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("previous_start_time", models.DateTimeField()),
                ("previous_end_time", models.DateTimeField()),
                (
                    "previous_venue",
                    models.CharField(
                        choices=[
                            ("venue1", "CNPAHS AVR"),
                            ("venue2", "CIT AVR"),
                            ("venue3", "CAS AVR"),
                            ("venue4", "ST AVR"),
                            ("venue5", "GYM"),
                            ("venue6", "INTERFAITH"),
                            ("venue7", "CTED MINI THEATRE"),
                            ("venue8", "CIT OPEN GROUNDS"),
                            ("venue9", "LIBRARY"),
                            ("venue10", "OPEN COURT"),
                            ("venue11", "MIS ROOM"),
                        ],
                        max_length=20,
                    ),
                ),
                ("rescheduled_at", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_history",
                        to="home.event",
                    ),
                ),
            ],
            options={
                "ordering": ["-rescheduled_at"],
            },
        ),
    ]
