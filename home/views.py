
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Event, EventScheduleHistory


def home(request):
    return render(request, "home/index.html")


def _event_json(event):
    history = event.schedule_history.first()
    return {
        "id": event.id,
        "title": event.title,
        "start": event.start_time.isoformat(),
        "end": event.end_time.isoformat(),
        "venue": event.venue,
        "department": event.department,
        "status": event.status,
        "rescheduling_reason": history.reason if history else "",
    }


def _parse_event_times(body):
    start_time = parse_datetime(body["start"])
    end_time = parse_datetime(body["end"])
    if start_time is None or end_time is None:
        raise ValueError("Invalid event time.")
    if timezone.is_naive(start_time):
        start_time = timezone.make_aware(start_time)
    if timezone.is_naive(end_time):
        end_time = timezone.make_aware(end_time)
    return start_time, end_time


def _validation_response(error):
    if "venue" in error.message_dict:
        return JsonResponse(
            {"message": error.message_dict["venue"][0]},
            status=409,
        )
    return JsonResponse({"message": error.messages[0]}, status=400)


@require_http_methods(["GET", "POST"])
def events_api(request):
    if request.method == "GET":
        events = Event.objects.prefetch_related("schedule_history")
        data = [_event_json(event) for event in events]
        return JsonResponse(data, safe=False)

    try:
        body = json.loads(request.body)
        start_time, end_time = _parse_event_times(body)
        event = Event(
            title=body["title"],
            start_time=start_time,
            end_time=end_time,
            venue=body["venue"],
            department=body["department"],
            status=Event.Status.PENDING,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({"message": "Invalid event data."}, status=400)

    try:
        event.full_clean()
    except ValidationError as error:
        return _validation_response(error)

    event.save()

    return JsonResponse(
        {"id": event.id, "message": "Event saved"},
        status=201,
    )


@require_http_methods(["GET", "PUT", "PATCH"])
def event_detail_api(request, event_id):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({"message": "Event not found."}, status=404)

    if request.method == "GET":
        return JsonResponse(_event_json(event))

    try:
        body = json.loads(request.body)
        requested_status = body.get("status", event.status)
        if requested_status not in Event.Status.values:
            raise ValueError("Invalid event status.")
        if requested_status == Event.Status.RESCHEDULED:
            if not body.get("reschedule_start") or not body.get("reschedule_end"):
                return JsonResponse(
                    {"message": "Enter the new start and end dates and times."},
                    status=400,
                )
            start_time, end_time = _parse_event_times(
                {
                    "start": body["reschedule_start"],
                    "end": body["reschedule_end"],
                }
            )
        else:
            start_time, end_time = _parse_event_times(body)
        title = body["title"]
        department = body["department"]
        venue = body["venue"]
        reason = body.get("rescheduling_reason", "")
        if not isinstance(reason, str):
            raise ValueError("Invalid rescheduling reason.")
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({"message": "Invalid event data."}, status=400)

    previous_start = event.start_time
    previous_end = event.end_time
    previous_venue = event.venue

    try:
        status, schedule_changed = event.resolve_status(
            requested_status, start_time, end_time, venue
        )
        event.title = title
        event.department = department
        event.venue = venue
        event.start_time = start_time
        event.end_time = end_time
        event.status = status
        event.full_clean()
    except ValidationError as error:
        return _validation_response(error)

    with transaction.atomic():
        event.save()
        if status == Event.Status.RESCHEDULED and schedule_changed:
            EventScheduleHistory.objects.create(
                event=event,
                previous_start_time=previous_start,
                previous_end_time=previous_end,
                previous_venue=previous_venue,
                reason=reason,
            )

    return JsonResponse(_event_json(event))
