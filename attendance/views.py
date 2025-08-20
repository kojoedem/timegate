from math import radians, sin, cos, sqrt, atan2

from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Attendance, OfficeLocation, AllowedIP
from .serializers import AttendActionSerializer, AttendanceSerializer


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

def location_allowed(request, lat=None, lon=None):
    office = OfficeLocation.objects.first()
    if not office:
        # If no office configured, deny for safety
        return False, "No office location configured"

    # GPS check
    if lat is not None and lon is not None:
        dist = haversine_m(lat, lon, office.latitude, office.longitude)
        if dist <= office.allowed_radius:
            return True, None

    # IP check
    client_ip = get_client_ip(request)
    if client_ip and AllowedIP.objects.filter(ip_address=client_ip).exists():
        return True, None

    return False, "Outside allowed location or IP"

def get_open_attendance(user):
    return Attendance.objects.filter(user=user, clock_out__isnull=True).order_by("-clock_in").first()

class ClockInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AttendActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data.get("latitude")
        lon = serializer.validated_data.get("longitude")

        allowed, reason = location_allowed(request, lat, lon)
        if not allowed:
            return Response({"detail": f"Clock-in denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)

        open_att = get_open_attendance(request.user)
        if open_att:
            return Response({"detail": "You already have an active session."}, status=status.HTTP_400_BAD_REQUEST)

        att = Attendance.objects.create(user=request.user, clock_in=now())
        return Response(AttendanceSerializer(att).data, status=status.HTTP_201_CREATED)

class BreakStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        att = get_open_attendance(request.user)
        if not att:
            return Response({"detail": "No active session to start break."}, status=status.HTTP_400_BAD_REQUEST)
        if att.break_start and not att.break_end:
            return Response({"detail": "Already on break."}, status=status.HTTP_400_BAD_REQUEST)

        if att.on_break:
            return Response({"error": "Break already started."}, status=status.HTTP_400_BAD_REQUEST)

        att.break_start = now()
        att.break_end = None
        att.save()
        return Response(AttendanceSerializer(att).data)

class BreakEndView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        att = get_open_attendance(request.user)
        if not att:
            return Response({"detail": "No active session to end break."}, status=status.HTTP_400_BAD_REQUEST)
        if not att.on_break:
            return Response({"detail": "No ongoing break to end."}, status=status.HTTP_400_BAD_REQUEST)
        att.break_end = now()
        att.save()
        return Response(AttendanceSerializer(att).data)

class ClockOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        att = get_open_attendance(request.user)
        if not att:
            return Response({"detail": "No active session to clock out."}, status=status.HTTP_400_BAD_REQUEST)

        # Optionally enforce location on clock-out too:
        serializer = AttendActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data.get("latitude")
        lon = serializer.validated_data.get("longitude")

        allowed, reason = location_allowed(request, lat, lon)
        if not allowed:
            return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)

        att.clock_out = now()

        # compute total seconds worked, subtracting break if present
        total = int((att.clock_out - att.clock_in).total_seconds())
        if att.break_start and att.break_end and att.break_end > att.break_start:
            total -= int((att.break_end - att.break_start).total_seconds())
        att.total_seconds = max(total, 0)
        att.save()
        return Response(AttendanceSerializer(att).data)

class TodayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        att = get_open_attendance(request.user)
        if att:
            return Response(AttendanceSerializer(att).data)
        return Response({"detail": "No active session."})
