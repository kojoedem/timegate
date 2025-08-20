
from django.urls import path
from .views import ClockInView, BreakStartView, BreakEndView, ClockOutView, TodayStatusView, FaceLoginView

urlpatterns = [
    path("face-login/", FaceLoginView.as_view(), name="face-login"),
    path("clock-in/", ClockInView.as_view(), name="clock-in"),
    path("break-start/", BreakStartView.as_view(), name="break-start"),
    path("break-end/", BreakEndView.as_view(), name="break-end"),
    path("clock-out/", ClockOutView.as_view(), name="clock-out"),
    path("today/", TodayStatusView.as_view(), name="today-status"),
]


