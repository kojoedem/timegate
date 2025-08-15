from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
from urllib import request

from django.utils.timezone import now
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, authentication

from .models import Attendance, OfficeLocation, AllowedIP
from .serializers import AttendActionSerializer, AttendanceSerializer

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils.timezone import now
from .models import Attendance
import math
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


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
        if not att.break_start or att.break_end:
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

class AttendanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action):
        """
        Handles user interactions with the system.
        Actions: clock_in, start_break, end_break, clock_out
        """
        user = request.user
        attendance, created = Attendance.objects.get_or_create(user=user, date=now().date())

        if action == "clock_in":
            if attendance.clock_in_time:
                return Response({"error": "Already clocked in."}, status=status.HTTP_400_BAD_REQUEST)
            attendance.clock_in_time = now()
            attendance.save()
            return Response({"message": "Clocked in successfully."})

        elif action == "start_break":
            if not attendance.clock_in_time:
                return Response({"error": "You must clock in first."}, status=status.HTTP_400_BAD_REQUEST)
            if attendance.break_start_time:
                return Response({"error": "Break already started."}, status=status.HTTP_400_BAD_REQUEST)
            attendance.break_start_time = now()
            attendance.save()
            return Response({"message": "Break started successfully."})

        elif action == "end_break":
            if not attendance.break_start_time:
                return Response({"error": "You must start a break first."}, status=status.HTTP_400_BAD_REQUEST)
            if attendance.break_end_time:
                return Response({"error": "Break already ended."}, status=status.HTTP_400_BAD_REQUEST)
            attendance.break_end_time = now()
            attendance.save()
            return Response({"message": "Break ended successfully."})

        elif action == "clock_out":
            if not attendance.clock_in_time:
                return Response({"error": "You must clock in first."}, status=status.HTTP_400_BAD_REQUEST)
            if attendance.clock_out_time:
                return Response({"error": "Already clocked out."}, status=status.HTTP_400_BAD_REQUEST)
            attendance.clock_out_time = now()
            attendance.save()
            return Response({"message": "Clocked out successfully."})

        else:
            return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)
        

# Company's fixed coordinates
COMPANY_LAT = 5.6037  # Example: Accra
COMPANY_LON = -0.1870
ALLOWED_RADIUS_METERS = 1  # 1-meter radius

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@method_decorator(csrf_exempt, name="dispatch")
# class GeolocationClockInView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             user_lat = float(request.data.get("latitude"))
#             user_lon = float(request.data.get("longitude"))

#             distance = haversine(COMPANY_LAT, COMPANY_LON, user_lat, user_lon)

#             if distance <= ALLOWED_RADIUS_METERS:
#                 # Process normal clock-in logic here
#                 return JsonResponse({"status": "success", "message": "Clock-in allowed"})
#             else:
#                 return JsonResponse({"status": "error", "message": f"Too far from office ({distance:.2f}m away)"})
#         except (TypeError, ValueError):
#             return JsonResponse({"status": "error", "message": "Invalid latitude or longitude"})
# filepath: /media/koliko/BIG/KOLIKO/DEVS/PROJECT-SELF/timegate/attendance/views.py


# class GeolocationClockInView(APIView):
#     permission_classes = [IsAuthenticated]
   

#     def post(self, request):
#         user = request.user
#         user_lat = float(request.data.get("latitude"))
#         user_lon = float(request.data.get("longitude"))
#         print("Raw data received:", request.data)
#         # Calculate distance using haversine
#         distance = haversine(COMPANY_LAT, COMPANY_LON, user_lat, user_lon)

#         if distance <= ALLOWED_RADIUS_METERS:
#             # Get today's attendance record or create a new one
#             attendance_qs = Attendance.objects.filter(user=user, date=now().date())
#             if attendance_qs.exists():
#                 if attendance_qs.count() > 1:
#                     # Handle duplicate records (optional: log or clean up duplicates)
#                     attendance_qs = attendance_qs.order_by("-clock_in")[:1]
#                 attendance = attendance_qs.first()
#                 if attendance.clock_in:
#                     return JsonResponse({"status": "error", "message": "Already clocked in"})
#             else:
#                 attendance = Attendance.objects.create(user=user, clock_in=now(), date=now().date())

#             attendance.clock_in = now()
#             attendance.save()
#             return JsonResponse({"status": "success", "message": "Clock-in successful"})
#         else:
#             return JsonResponse({"status": "error", "message": f"Too far from office ({distance:.2f}m away)"})

class GeolocationClockInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print("Raw data received:", request.data)  # Debugging log

        user = request.user
        lat_str = request.data.get("latitude")
        lon_str = request.data.get("longitude")

        # Validate presence of coordinates
        if lat_str is None or lon_str is None:
            return JsonResponse(
                {"status": "error", "message": "Latitude and longitude are required"},
                status=400
            )

        # Validate numeric format
        try:
            user_lat = float(lat_str)
            user_lon = float(lon_str)
        except ValueError:
            return JsonResponse(
                {"status": "error", "message": "Invalid latitude or longitude format"},
                status=400
            )

        # Calculate distance using haversine
        distance = haversine(COMPANY_LAT, COMPANY_LON, user_lat, user_lon)

        if distance <= ALLOWED_RADIUS_METERS:
            # Get today's attendance record
            attendance_qs = Attendance.objects.filter(user=user, date=now().date())
            if attendance_qs.exists():
                if attendance_qs.count() > 1:
                    attendance_qs = attendance_qs.order_by("-clock_in")[:1]
                attendance = attendance_qs.first()
                if attendance.clock_in:
                    return JsonResponse(
                        {"status": "error", "message": "Already clocked in"},
                        status=400
                    )
            else:
                attendance = Attendance.objects.create(user=user, clock_in=now(), date=now().date())

            attendance.clock_in = now()
            attendance.save()
            return JsonResponse({"status": "success", "message": "Clock-in successful"})
        else:
            return JsonResponse(
                {"status": "error", "message": f"Too far from office ({distance:.2f}m away)"},
                status=400
            )
