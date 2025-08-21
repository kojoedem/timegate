from django.urls import path
from .views import register, clocking_page, UserProfileView, UserEditView, PolicyEditView

urlpatterns = [
    path("", clocking_page, name="clocking_page"),
    path("register/", register, name="register"),
    path("profile/", UserProfileView.as_view(), name="profile_page"),
    path("user/<int:user_id>/edit/", UserEditView.as_view(), name="edit_user"),
    path("policy/<int:group_id>/edit/", PolicyEditView.as_view(), name="edit_policy"),
]
