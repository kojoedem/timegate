from math import radians, sin, cos, sqrt, atan2
import cv2
import numpy as np
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token

from .models import Attendance, OfficeLocation, AllowedIP, Profile, GroupTimePolicy
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


def verify_user_face(user, image_to_verify):
    try:
        profile = user.profile
        if not profile.reference_image or not hasattr(profile.reference_image, 'path'):
            return False, "No reference image for user."
    except Profile.DoesNotExist:
        return False, "No profile for user."

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # 1. "Train" on the user's reference image
    image_path = profile.reference_image.path
    ref_img = cv2.imread(image_path)
    if ref_img is None:
        return False, "Could not read reference image file."
    gray_ref_img = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

    ref_faces = face_cascade.detectMultiScale(gray_ref_img, 1.1, 5)
    if len(ref_faces) == 0:
        return False, "Could not find face in reference image."

    (x, y, w, h) = ref_faces[0]
    face_to_train = gray_ref_img[y:y+h, x:x+w]

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([face_to_train], np.array([user.id]))

    # 2. Predict on the new image
    uploaded_img_data = image_to_verify.read()
    np_arr = np.frombuffer(uploaded_img_data, np.uint8)
    uploaded_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    gray_uploaded_img = cv2.cvtColor(uploaded_img, cv2.COLOR_BGR2GRAY)

    uploaded_faces = face_cascade.detectMultiScale(gray_uploaded_img, 1.1, 5)
    if len(uploaded_faces) == 0:
        return False, "No face detected in provided image."

    (x, y, w, h) = uploaded_faces[0]
    label, confidence = recognizer.predict(gray_uploaded_img[y:y+h, x:x+w])

    # 3. Check confidence
    CONFIDENCE_THRESHOLD = 85
    if label == user.id and confidence < CONFIDENCE_THRESHOLD:
        return True, "Face verified."
    else:
        return False, f"Face does not match. Confidence: {confidence}"


class ClockInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AttendActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data.get("latitude")
        lon = serializer.validated_data.get("longitude")

        # Check group-based time policy
        user = request.user
        current_time = now().time()
        user_groups = user.groups.all()

        if user_groups:
            group = user_groups.first()
            if hasattr(group, 'time_policy'):
                policy = group.time_policy
                if not (policy.start_time <= current_time <= policy.end_time):
                    return Response(
                        {"detail": f"Clock-in denied. Your group can only clock in between {policy.start_time.strftime('%H:%M')} and {policy.end_time.strftime('%H:%M')}."},
                        status=status.HTTP_403_FORBIDDEN
                    )

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

        serializer = AttendActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data.get("latitude")
        lon = serializer.validated_data.get("longitude")
        face_capture = serializer.validated_data.get("face_capture")

        # Face verification
        if not face_capture:
            return Response({"detail": "Face capture is required for clock-out."}, status=status.HTTP_400_BAD_REQUEST)

        verified, reason = verify_user_face(request.user, face_capture)
        if not verified:
            return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)

        # Location check
        allowed, reason = location_allowed(request, lat, lon)
        if not allowed:
            return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)

        att.clock_out = now()

        # Compute total seconds worked
        total = int((att.clock_out - att.clock_in).total_seconds())
        if att.break_start and att.break_end and att.break_end > att.break_start:
            total -= int((att.break_end - att.break_start).total_seconds())
        att.total_seconds = max(total, 0)
        att.save()

        # Invalidate token to log out
        request.user.auth_token.delete()

        return Response(AttendanceSerializer(att).data)

from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponse
import csv
import datetime
from .forms import UserRegistrationForm


class TodayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        att = get_open_attendance(request.user)
        if att:
            return Response(AttendanceSerializer(att).data)
        return Response({"detail": "No active session."})


def clocking_page(request):
    return render(request, 'attendance/clocking.html')


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            # Face encoding logic will be added here in a later step.
            return redirect('clocking_page')
    else:
        form = UserRegistrationForm()
    return render(request, 'attendance/register.html', {'form': form})


class UserProfileView(LoginRequiredMixin, View):
    def get(self, request):
        attendances = Attendance.objects.filter(user=request.user).order_by('-date', '-clock_in')
        context = {
            'attendances': attendances
        }
        return render(request, 'attendance/profile.html', context)

    def post(self, request):
        new_image = request.FILES.get('reference_image')
        if new_image:
            profile = request.user.profile
            profile.reference_image = new_image
            profile.save()
            messages.success(request, 'Your profile picture has been updated successfully!')

        return redirect('profile_page')


class FaceLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = AttendActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_image_file = serializer.validated_data.get("face_capture")

        if not uploaded_image_file:
            return Response({"detail": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Prepare training data
        profiles = Profile.objects.filter(reference_image__isnull=False).exclude(reference_image='')
        if not profiles.exists():
            return Response({"detail": "No registered faces in the system."}, status=status.HTTP_400_BAD_REQUEST)

        faces = []
        labels = []

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        for profile in profiles:
            # Read the image from the storage
            image_path = profile.reference_image.path
            ref_img = cv2.imread(image_path)
            gray_ref_img = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

            # Detect face in the reference image
            detected_faces = face_cascade.detectMultiScale(gray_ref_img, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            if len(detected_faces) > 0:
                (x, y, w, h) = detected_faces[0]
                faces.append(gray_ref_img[y:y+h, x:x+w])
                labels.append(profile.user.id)

        if not faces:
            return Response({"detail": "Could not extract faces from reference images."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 2. Train the recognizer
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, np.array(labels))

        # 3. Process the uploaded image
        uploaded_img_data = uploaded_image_file.read()
        np_arr = np.frombuffer(uploaded_img_data, np.uint8)
        uploaded_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        gray_uploaded_img = cv2.cvtColor(uploaded_img, cv2.COLOR_BGR2GRAY)

        # Detect face in the uploaded image
        detected_faces_uploaded = face_cascade.detectMultiScale(gray_uploaded_img, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(detected_faces_uploaded) == 0:
            return Response({"detail": "No face detected in the provided image."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Make a prediction
        (x, y, w, h) = detected_faces_uploaded[0]
        predicted_label, confidence = recognizer.predict(gray_uploaded_img[y:y+h, x:x+w])

        # 5. Validate prediction and log in
        # For LBPH, lower confidence is better. 0 is a perfect match.
        CONFIDENCE_THRESHOLD = 80
        if confidence < CONFIDENCE_THRESHOLD:
            try:
                user = User.objects.get(id=predicted_label)
                token, created = Token.objects.get_or_create(user=user)
                return Response({'token': token.key, 'username': user.username})
            except User.DoesNotExist:
                return Response({"detail": "Identified user not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "Could not identify face."}, status=status.HTTP_400_BAD_REQUEST)


class AdminDashboardView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def get(self, request):
        # Get users who are currently clocked in and not on break
        clocked_in_users = Attendance.objects.filter(clock_out__isnull=True, break_start__isnull=True).select_related('user')

        # Get users who are currently on break
        on_break_users = Attendance.objects.filter(break_start__isnull=False, break_end__isnull=True).select_related('user')

        context = {
            'clocked_in_users': clocked_in_users,
            'on_break_users': on_break_users,
            'total_users': User.objects.count(),
            'total_clocked_in': clocked_in_users.count(),
            'total_on_break': on_break_users.count(),
        }
        return render(request, 'attendance/admin_dashboard.html', context)

    def post(self, request):
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        if not start_date_str or not end_date_str:
            # Handle error: dates not provided
            messages.error(request, "Please provide both a start and end date.")
            return redirect('admin_dashboard')

        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        attendances = Attendance.objects.filter(date__range=[start_date, end_date]).order_by('user', 'date')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date_str}_to_{end_date_str}.csv"'

        writer = csv.writer(response)
        writer.writerow(['User', 'Date', 'Clock In', 'Clock Out', 'Total Hours'])

        for att in attendances:
            total_hours = round(att.total_seconds / 3600, 2) if att.total_seconds else 0
            writer.writerow([
                att.user.username,
                att.date,
                att.clock_in.strftime('%Y-%m-%d %H:%M:%S') if att.clock_in else '',
                att.clock_out.strftime('%Y-%m-%d %H:%M:%S') if att.clock_out else '',
                total_hours
            ])

        return response
