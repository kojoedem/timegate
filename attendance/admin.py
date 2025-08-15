
from django.contrib import admin
from .models import OfficeLocation, AllowedIP, Attendance

@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "allowed_radius")

@admin.register(AllowedIP)
class AllowedIPAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "description")

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("user", "clock_in", "clock_out", "on_break", "total_seconds")
    list_filter = ("user", "clock_in")
