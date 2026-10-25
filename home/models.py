from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

VENUES = [
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
]


class Event(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        RESCHEDULED = "rescheduled", "Rescheduled"
        CANCELED = "canceled", "Canceled"

    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.PENDING, Status.APPROVED, Status.CANCELED},
        Status.APPROVED: {Status.APPROVED, Status.RESCHEDULED, Status.CANCELED},
        Status.RESCHEDULED: {Status.RESCHEDULED, Status.APPROVED, Status.CANCELED},
        Status.CANCELED: {Status.CANCELED},
    }

    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    department = models.TextField(blank=True)
    end_time = models.DateTimeField()
    venue = models.CharField(max_length=20, choices=VENUES)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def schedule_changed(self, start_time, end_time, venue):
        return (
            self.start_time != start_time
            or self.end_time != end_time
            or self.venue != venue
        )

    def resolve_status(self, requested_status, start_time, end_time, venue):
        schedule_changed = self.schedule_changed(start_time, end_time, venue)
        status = requested_status

        if (
            self.status == self.Status.APPROVED
            and schedule_changed
            and status == self.Status.APPROVED
        ):
            status = self.Status.RESCHEDULED

        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if status not in allowed:
            raise ValidationError(
                {"status": "This status change is not allowed for the current event."}
            )

        if (
            start_time < timezone.now()
            and (
                start_time != self.start_time
                or (
                    requested_status == self.Status.RESCHEDULED
                    and schedule_changed
                )
            )
        ):
            raise ValidationError(
                {
                    "status": (
                        "An event cannot be rescheduled to a date and time in the past."
                    )
                }
            )

        if status == self.Status.RESCHEDULED and not schedule_changed:
            raise ValidationError(
                {"status": "Rescheduling requires a new date, time, or venue."}
            )

        return status, schedule_changed

    def clean(self):
        super().clean()

        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be later than start time."})

        if not self.venue or not self.start_time or not self.end_time:
            return

        overlapping_events = Event.objects.filter(
            venue=self.venue,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(status=Event.Status.CANCELED)
        if self.pk:
            overlapping_events = overlapping_events.exclude(pk=self.pk)

        if overlapping_events.exists():
            raise ValidationError({"venue": "This venue is already booked during that time."})

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class EventScheduleHistory(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="schedule_history",
    )
    previous_start_time = models.DateTimeField()
    previous_end_time = models.DateTimeField()
    previous_venue = models.CharField(max_length=20, choices=VENUES)
    reason = models.TextField(blank=True, default="")
    rescheduled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rescheduled_at"]

    def __str__(self):
        return f"History for {self.event_id} at {self.rescheduled_at}"
