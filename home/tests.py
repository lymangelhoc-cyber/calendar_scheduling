import json
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event


class EventOverlapTests(TestCase):
    def setUp(self):
        self.start = timezone.now().replace(second=0, microsecond=0)
        self.end = self.start + timedelta(hours=1)
        Event.objects.create(
            title="Existing event",
            department="Department",
            venue="venue1",
            start_time=self.start,
            end_time=self.end,
        )

    def make_event(self, *, venue="venue1", start=None, end=None):
        return Event(
            title="New event",
            department="Department",
            venue=venue,
            start_time=start or self.start,
            end_time=end or self.end,
        )

    def test_model_rejects_overlapping_event_at_same_venue(self):
        with self.assertRaises(ValidationError):
            self.make_event().full_clean()

    def test_model_allows_adjacent_event_at_same_venue(self):
        event = self.make_event(start=self.end, end=self.end + timedelta(hours=1))
        event.full_clean()

    def test_model_allows_overlapping_event_at_different_venue(self):
        self.make_event(venue="venue2").full_clean()

    def test_model_ignores_canceled_events(self):
        Event.objects.filter(title="Existing event").update(status=Event.Status.CANCELED)
        self.make_event().full_clean()

    def test_api_rejects_overlapping_event(self):
        response = self.client.post(
            reverse("events_api"),
            data=json.dumps(
                {
                    "title": "New event",
                    "department": "Department",
                    "venue": "venue1",
                    "start": self.start.isoformat(),
                    "end": self.end.isoformat(),
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already booked", response.json()["message"])
        self.assertEqual(Event.objects.count(), 1)

    def test_api_accepts_adjacent_event(self):
        response = self.client.post(
            reverse("events_api"),
            data=json.dumps(
                {
                    "title": "Next event",
                    "department": "Department",
                    "venue": "venue1",
                    "start": self.end.isoformat(),
                    "end": (self.end + timedelta(hours=1)).isoformat(),
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 2)

    def test_api_makes_naive_datetimes_aware(self):
        response = self.client.post(
            reverse("events_api"),
            data=json.dumps(
                {
                    "title": "New event",
                    "department": "Department",
                    "venue": "venue2",
                    "start": "2026-10-28T02:00:00",
                    "end": "2026-10-28T03:00:00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        event = Event.objects.get(pk=response.json()["id"])
        self.assertTrue(timezone.is_aware(event.start_time))
        self.assertTrue(timezone.is_aware(event.end_time))


class EventUpdateTests(TestCase):
    def setUp(self):
        self.start = timezone.now().replace(second=0, microsecond=0)
        self.end = self.start + timedelta(hours=1)
        self.event = Event.objects.create(
            title="Existing event",
            department="Department",
            venue="venue1",
            start_time=self.start,
            end_time=self.end,
        )
        self.other = Event.objects.create(
            title="Other event",
            department="Department",
            venue="venue1",
            start_time=self.end,
            end_time=self.end + timedelta(hours=1),
        )

    def update(self, event, **overrides):
        payload = {
            "title": event.title,
            "department": event.department,
            "venue": event.venue,
            "start": event.start_time.isoformat(),
            "end": event.end_time.isoformat(),
            "status": event.status,
        }
        payload.update(overrides)
        return self.client.put(
            reverse("event_detail_api", args=[event.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_update_saves_changes(self):
        new_end = self.start + timedelta(minutes=30)
        response = self.update(
            self.event,
            title="Updated title",
            department="MIS",
            venue="venue2",
            end=new_end.isoformat(),
            status="approved",
        )

        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Updated title")
        self.assertEqual(self.event.department, "MIS")
        self.assertEqual(self.event.venue, "venue2")
        self.assertEqual(self.event.status, Event.Status.APPROVED)

    def test_update_excludes_current_event_from_conflict_check(self):
        response = self.update(self.event, title="Same slot")
        self.assertEqual(response.status_code, 200)

    def test_update_rejects_overlap_with_another_event(self):
        response = self.update(
            self.event,
            end=self.other.end_time.isoformat(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already booked", response.json()["message"])

    def test_approving_rechecks_conflicts(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.RESCHEDULED)
        Event.objects.create(
            title="Blocking event",
            department="Department",
            venue="venue1",
            start_time=self.start,
            end_time=self.end,
        )
        self.event.refresh_from_db()
        response = self.update(self.event, status="approved")
        self.assertEqual(response.status_code, 409)


class EventStatusWorkflowTests(TestCase):
    def setUp(self):
        self.start = timezone.now().replace(second=0, microsecond=0)
        self.end = self.start + timedelta(hours=1)
        self.event = Event.objects.create(
            title="Workflow event",
            department="Department",
            venue="venue1",
            start_time=self.start,
            end_time=self.end,
        )

    def update(self, event, **overrides):
        payload = {
            "title": event.title,
            "department": event.department,
            "venue": event.venue,
            "start": event.start_time.isoformat(),
            "end": event.end_time.isoformat(),
            "status": event.status,
        }
        payload.update(overrides)
        return self.client.put(
            reverse("event_detail_api", args=[event.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_create_always_starts_pending(self):
        response = self.client.post(
            reverse("events_api"),
            data=json.dumps(
                {
                    "title": "New event",
                    "department": "Department",
                    "venue": "venue2",
                    "start": (self.end + timedelta(hours=1)).isoformat(),
                    "end": (self.end + timedelta(hours=2)).isoformat(),
                    "status": "approved",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        created = Event.objects.get(pk=response.json()["id"])
        self.assertEqual(created.status, Event.Status.PENDING)

    def test_pending_cannot_become_rescheduled(self):
        response = self.update(
            self.event,
            status="rescheduled",
            start=(self.start + timedelta(hours=3)).isoformat(),
            end=(self.end + timedelta(hours=3)).isoformat(),
        )
        self.assertEqual(response.status_code, 400)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.PENDING)

    def test_approving_pending_event_saves_approved(self):
        response = self.update(self.event, status="approved")
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.APPROVED)

    def test_approved_schedule_change_becomes_rescheduled_and_records_history(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        new_start = self.start + timedelta(days=1)
        new_end = new_start + timedelta(hours=1)
        response = self.update(
            self.event,
            status="approved",
            venue="venue2",
            start=new_start.isoformat(),
            end=new_end.isoformat(),
        )
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.RESCHEDULED)
        self.assertEqual(self.event.venue, "venue2")
        history = self.event.schedule_history.get()
        self.assertEqual(history.previous_venue, "venue1")
        self.assertEqual(history.previous_start_time, self.start)
        self.assertEqual(history.previous_end_time, self.end)

    def test_explicit_reschedule_saves_destination_and_reason(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        new_start = timezone.now() + timedelta(days=2)
        new_end = new_start + timedelta(hours=2)
        response = self.update(
            self.event,
            status="rescheduled",
            reschedule_start=new_start.isoformat(),
            reschedule_end=new_end.isoformat(),
            rescheduling_reason="Venue maintenance",
        )

        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.RESCHEDULED)
        self.assertEqual(self.event.start_time, new_start)
        self.assertEqual(self.event.end_time, new_end)
        history = self.event.schedule_history.get()
        self.assertEqual(history.previous_start_time, self.start)
        self.assertEqual(history.previous_end_time, self.end)
        self.assertEqual(history.reason, "Venue maintenance")
        self.assertEqual(response.json()["rescheduling_reason"], "Venue maintenance")

    def test_explicit_reschedule_requires_destination_times(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        response = self.update(self.event, status="rescheduled")

        self.assertEqual(response.status_code, 400)
        self.assertIn("new start and end", response.json()["message"])
        self.event.refresh_from_db()
        self.assertEqual(self.event.start_time, self.start)
        self.assertEqual(self.event.status, Event.Status.APPROVED)
        self.assertEqual(self.event.schedule_history.count(), 0)

    def test_explicit_reschedule_rejects_end_before_start(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        new_start = timezone.now() + timedelta(days=2)
        response = self.update(
            self.event,
            status="rescheduled",
            reschedule_start=new_start.isoformat(),
            reschedule_end=(new_start - timedelta(minutes=1)).isoformat(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "End time must be later than start time.")
        self.event.refresh_from_db()
        self.assertEqual(self.event.start_time, self.start)
        self.assertEqual(self.event.status, Event.Status.APPROVED)

    def test_explicit_reschedule_rejects_a_past_destination(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        past_start = timezone.now() - timedelta(hours=2)
        response = self.update(
            self.event,
            status="rescheduled",
            reschedule_start=past_start.isoformat(),
            reschedule_end=(past_start + timedelta(hours=1)).isoformat(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("past", response.json()["message"])
        self.event.refresh_from_db()
        self.assertEqual(self.event.start_time, self.start)
        self.assertEqual(self.event.status, Event.Status.APPROVED)

    def test_rescheduling_to_a_past_date_and_time_is_rejected(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        past_start = timezone.now() - timedelta(hours=2)
        response = self.update(
            self.event,
            status="approved",
            venue="venue2",
            start=past_start.isoformat(),
            end=(past_start + timedelta(hours=1)).isoformat(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("past", response.json()["message"])
        self.event.refresh_from_db()
        self.assertEqual(self.event.start_time, self.start)
        self.assertEqual(self.event.status, Event.Status.APPROVED)
        self.assertEqual(self.event.schedule_history.count(), 0)

    def test_cannot_mark_rescheduled_without_schedule_change(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.APPROVED)
        self.event.refresh_from_db()
        response = self.update(self.event, status="rescheduled")
        self.assertEqual(response.status_code, 400)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.APPROVED)
        self.assertEqual(self.event.schedule_history.count(), 0)

    def test_canceled_cannot_be_approved(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.CANCELED)
        self.event.refresh_from_db()
        response = self.update(self.event, status="approved")
        self.assertEqual(response.status_code, 400)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.CANCELED)

    def test_canceled_cannot_be_rescheduled(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.CANCELED)
        self.event.refresh_from_db()
        response = self.update(
            self.event,
            status="rescheduled",
            start=(self.start + timedelta(hours=4)).isoformat(),
            end=(self.end + timedelta(hours=4)).isoformat(),
        )
        self.assertEqual(response.status_code, 400)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.CANCELED)

    def test_rescheduled_event_still_blocks_venue(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.RESCHEDULED)
        overlapping = Event(
            title="Conflict",
            department="Department",
            venue="venue1",
            start_time=self.start,
            end_time=self.end,
        )
        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_approving_rescheduled_event_rechecks_conflicts(self):
        Event.objects.filter(pk=self.event.pk).update(status=Event.Status.RESCHEDULED)
        Event.objects.create(
            title="Blocking event",
            department="Department",
            venue="venue2",
            start_time=self.start,
            end_time=self.end,
            status=Event.Status.PENDING,
        )
        self.event.refresh_from_db()
        response = self.update(self.event, status="approved", venue="venue2")
        self.assertEqual(response.status_code, 409)
