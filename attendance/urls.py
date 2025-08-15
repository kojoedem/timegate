
from django.urls import path
from .views import ClockInView, BreakStartView, BreakEndView, ClockOutView, TodayStatusView

from django.urls import path
from .views import AttendanceView
from .views import GeolocationClockInView

urlpatterns = [
    path("clock-in/", ClockInView.as_view(), name="clock-in"),
    path("break-start/", BreakStartView.as_view(), name="break-start"),
    path("break-end/", BreakEndView.as_view(), name="break-end"),
    path("clock-out/", ClockOutView.as_view(), name="clock-out"),
    path("today/", TodayStatusView.as_view(), name="today-status"),
    path("attendance/<str:action>/", AttendanceView.as_view(), name="attendance"),
    path("geolocation-clock-in/", GeolocationClockInView.as_view(), name="geolocation-clock-in"),
]


