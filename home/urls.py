from django.urls import path
from . import views    

urlpatterns = [
    path("", views.home, name="home"),
    path("api/events/", views.events_api, name="events_api"),
    path("api/events/<int:event_id>/", views.event_detail_api, name="event_detail_api"),
]
