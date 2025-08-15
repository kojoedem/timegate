
from rest_framework import serializers
from .models import Attendance

class AttendActionSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ["id", "user", "clock_in", "clock_out", "break_start", "break_end", "total_seconds", "on_break"]
        read_only_fields = fields
