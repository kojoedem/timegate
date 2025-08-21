
import base64
import uuid
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Attendance

# Custom image field - handles base 64 encoded images
class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # base64 encoded image - decode
            format, imgstr = data.split(';base64,') # format ~= data:image/X,
            ext = format.split('/')[-1] # guess file extension
            id = uuid.uuid4()
            data = ContentFile(base64.b64decode(imgstr), name=id.urn[9:] + '.' + ext)
        return super().to_internal_value(data)

class AttendActionSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    face_capture = Base64ImageField(required=False, allow_null=True)

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ["id", "user", "clock_in", "clock_out", "break_start", "break_end", "total_seconds", "on_break"]
        read_only_fields = fields
