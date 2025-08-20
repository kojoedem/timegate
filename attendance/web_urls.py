from django.urls import path
from .views import register, clocking_page, UserProfileView, AdminDashboardView

urlpatterns = [
    path("", clocking_page, name="clocking_page"),
    path("register/", register, name="register"),
    path("profile/", UserProfileView.as_view(), name="profile_page"),
    path("admin-dashboard/", AdminDashboardView.as_view(), name="admin_dashboard"),
]
