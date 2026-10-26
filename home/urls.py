from django.urls import path
from . import views    

urlpatterns = [
    path("", views.home, name="home"),
    path("api/events/", views.events_api, name="events_api"),
    path("api/events/<int:event_id>/", views.event_detail_api, name="event_detail_api"),
    path("approved-events/", views.approved_events, name="approved_events"),
    path(
        "approved-events/<int:event_id>/done/",
        views.mark_event_done,
        name="mark_event_done",
    ),
    path("event-history/", views.event_history, name="event_history"),
    path("activity-logs/", views.activity_logs, name="activity_logs"),
]
