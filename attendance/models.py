
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class OfficeLocation(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    allowed_radius = models.IntegerField(default=50, help_text="Radius in meters")

    def __str__(self):
        return self.name

class AllowedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.ip_address

class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attendances")
    clock_in = models.DateTimeField(null=True, blank=True)
    break_start = models.DateTimeField(null=True, blank=True)
    break_end = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    total_seconds = models.PositiveIntegerField(default=0)
    date = models.DateField(default=now)

    class Meta:
        unique_together = ("user", "date")

    @property
    def on_break(self):
        return self.break_start is not None and self.break_end is None
