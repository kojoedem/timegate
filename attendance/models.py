
from django.db import models
from django.contrib.auth.models import User, Group
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

from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    reference_image = models.ImageField(upload_to='reference_images/', null=True, blank=True)
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_profiles',
        help_text="The supervisor for this user."
    )

    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Creates a Profile for a new User, or saves the existing one.
    This is idempotent and avoids race conditions.
    """
    if created:
        Profile.objects.get_or_create(user=instance)
    # Ensure the profile is saved on any user save
    instance.profile.save()


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


class GroupTimePolicy(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='time_policy')
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name_plural = "Group Time Policies"

    def __str__(self):
        return f"Time policy for {self.group.name}"
