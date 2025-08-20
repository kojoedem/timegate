from django.urls import path
from .views import register, clocking_page

urlpatterns = [
    path("", clocking_page, name="clocking_page"),
    path("register/", register, name="register"),
]
