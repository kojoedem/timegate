from math import radians, sin, cos, sqrt, atan2
import cv2
import numpy as np
from django.contrib.auth.models import User, Group
from django.contrib.auth import login, logout
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
import csv
import datetime
import os
from django.core.files.storage import default_storage
from django.db import transaction

from .models import Attendance, OfficeLocation, AllowedIP, Profile, GroupTimePolicy
from .serializers import AttendActionSerializer, AttendanceSerializer
from .forms import UserRegistrationForm, SingleUserCreationForm, GroupTimePolicyForm
from .utils import find_matching_face, verify_user_face, check_liveness

# Helper functions (unchanged)
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000; dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a)); return R * c
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR"); return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
def location_allowed(request, lat=None, lon=None):
    office = OfficeLocation.objects.first();
    if not office: return False, "No office location configured"
    if lat is not None and lon is not None and haversine_m(lat, lon, office.latitude, office.longitude) <= office.allowed_radius: return True, None
    if get_client_ip(request) and AllowedIP.objects.filter(ip_address=get_client_ip(request)).exists(): return True, None
    return False, "Outside allowed location or IP"
def get_open_attendance(user):
    return Attendance.objects.filter(user=user, clock_out__isnull=True).order_by("-clock_in").first()

# API Views (unchanged)
class ClockInView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        lat, lon = serializer.validated_data.get("latitude"), serializer.validated_data.get("longitude")
        user, current_time = request.user, now().time()
        policy = getattr(user.groups.first(), 'time_policy', None)
        if policy and not (policy.start_time <= current_time <= policy.end_time):
            return Response({"detail": f"Clock-in denied. Your group can only clock in between {policy.start_time.strftime('%H:%M')} and {policy.end_time.strftime('%H:%M')}."}, status=status.HTTP_403_FORBIDDEN)
        allowed, reason = location_allowed(request, lat, lon)
        if not allowed: return Response({"detail": f"Clock-in denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        if get_open_attendance(user): return Response({"detail": "You already have an active session."}, status=status.HTTP_400_BAD_REQUEST)
        att = Attendance.objects.create(user=user, clock_in=now()); return Response(AttendanceSerializer(att).data, status=status.HTTP_201_CREATED)
class BreakStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session to start break."}, status=status.HTTP_400_BAD_REQUEST)
        if att.break_start and not att.break_end: return Response({"detail": "Already on break."}, status=status.HTTP_400_BAD_REQUEST)
        att.break_start = now(); att.break_end = None; att.save(); return Response(AttendanceSerializer(att).data)
class BreakEndView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session to end break."}, status=status.HTTP_400_BAD_REQUEST)
        if not att.break_start or att.break_end: return Response({"detail": "No ongoing break to end."}, status=status.HTTP_400_BAD_REQUEST)
        att.break_end = now(); att.save(); return Response(AttendanceSerializer(att).data)
class ClockOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session to clock out."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        lat, lon, face_capture = serializer.validated_data.get("latitude"), serializer.validated_data.get("longitude"), serializer.validated_data.get("face_capture")
        if not face_capture: return Response({"detail": "Face capture is required for clock-out."}, status=status.HTTP_400_BAD_REQUEST)
        verified, reason = verify_user_face(request.user, face_capture)
        if not verified: return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        allowed, reason = location_allowed(request, lat, lon)
        if not allowed: return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        att.clock_out = now()
        total = int((att.clock_out - att.clock_in).total_seconds())
        if att.break_start and att.break_end and att.break_end > att.break_start: total -= int((att.break_end - att.break_start).total_seconds())
        att.total_seconds = max(total, 0); att.save()
        request.user.auth_token.delete(); logout(request); return Response(AttendanceSerializer(att).data)
class TodayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        att = get_open_attendance(request.user); return Response(AttendanceSerializer(att).data) if att else Response({"detail": "No active session."})
class FaceLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        face_capture = serializer.validated_data.get("face_capture")
        if not face_capture: return Response({"detail": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)
        user_id, _, reason = find_matching_face(face_capture)
        if user_id:
            try:
                user = User.objects.get(id=user_id); token, _ = Token.objects.get_or_create(user=user); login(request, user)
                return Response({'token': token.key, 'username': user.username})
            except User.DoesNotExist: return Response({"detail": "Identified user not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"detail": f"Could not identify face. Reason: {reason}"}, status=status.HTTP_400_BAD_REQUEST)

# Page Views
def clocking_page(request): return render(request, 'attendance/clocking.html')
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid(): form.save(); messages.success(request, 'Registration successful! You can now log in with your face.'); return redirect('clocking_page')
    else: form = UserRegistrationForm()
    return render(request, 'attendance/register.html', {'form': form})

# --- Consolidated Profile/Dashboard View ---
class UserProfileView(LoginRequiredMixin, View):
    def get_supervised_users(self, supervisor):
        return User.objects.filter(profile__supervisor=supervisor) if not supervisor.is_superuser else User.objects.all()

    def get(self, request):
        context = {'attendances': Attendance.objects.filter(user=request.user).order_by('-date', '-clock_in')}
        if request.user.is_staff:
            base_queryset = self.get_supervised_users(request.user)
            base_user_ids = base_queryset.values_list('id', flat=True)
            context.update({
                'is_supervisor': True,
                'supervised_users': base_queryset,
                'clocked_in_users': Attendance.objects.filter(user_id__in=base_user_ids, clock_out__isnull=True, break_start__isnull=True).select_related('user'),
                'on_break_users': Attendance.objects.filter(user_id__in=base_user_ids, clock_out__isnull=True, break_start__isnull=False, break_end__isnull=True).select_related('user'),
                'total_users': base_queryset.count(),
                'single_user_form': SingleUserCreationForm(),
                'time_policy_form': GroupTimePolicyForm(),
                'time_policies': GroupTimePolicy.objects.select_related('group').all(),
            })
            context['total_clocked_in'] = context['clocked_in_users'].count()
            context['total_on_break'] = context['on_break_users'].count()
        return render(request, 'attendance/profile.html', context)

    def post(self, request):
        action = request.POST.get('action')
        if not request.user.is_staff: action = 'update_picture' # Force non-staff to only update picture

        if action == 'update_picture': self.handle_update_picture(request)
        elif action == 'download_csv': return self.handle_download_csv(request)
        elif action == 'bulk_upload': self.handle_bulk_upload(request)
        elif action == 'add_single_user': self.handle_add_single_user(request)
        elif action == 'set_time_policy': self.handle_set_time_policy(request)
        elif action == 'delete_time_policy': self.handle_delete_time_policy(request)

        return redirect('profile_page')

    def handle_update_picture(self, request):
        new_image = request.FILES.get('reference_image')
        if new_image:
            request.user.profile.reference_image = new_image; request.user.profile.save()
            messages.success(request, 'Your profile picture has been updated successfully!')

    def handle_download_csv(self, request):
        start_date_str, end_date_str = request.POST.get('start_date'), request.POST.get('end_date')
        if not start_date_str or not end_date_str:
            messages.error(request, "Please provide both a start and end date."); return redirect('profile_page')
        start_date, end_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date(), datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        base_queryset = self.get_supervised_users(request.user)
        attendances = Attendance.objects.filter(user__in=base_queryset, date__range=[start_date, end_date]).order_by('user', 'date')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date_str}_to_{end_date_str}.csv"'
        writer = csv.writer(response); writer.writerow(['User', 'Date', 'Clock In', 'Clock Out', 'Total Hours'])
        for att in attendances:
            writer.writerow([att.user.username, att.date, att.clock_in.strftime('%H:%M'), att.clock_out.strftime('%H:%M') if att.clock_out else '', round(att.total_seconds / 3600, 2) if att.total_seconds else 0])
        return response

    def handle_bulk_upload(self, request):
        csv_file = request.FILES.get('csv_file')
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid .csv file.'); return
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines(); reader = csv.DictReader(decoded_file)
            created_count, errors = 0, []
            for row in reader:
                username = row.get('username')
                if not username or User.objects.filter(username=username).exists():
                    errors.append(f"Skipping user '{username}': missing or already exists."); continue
                with transaction.atomic():
                    user = User.objects.create_user(username=username, password=User.objects.make_random_password(), first_name=row.get('first_name', ''), last_name=row.get('last_name', ''))
                    # Profile is created by signal, just update it
                    user.profile.phone_number = row.get('phone_number', '')
                    user.profile.supervisor = request.user
                    user.profile.save()
                    created_count += 1
            if created_count > 0: messages.success(request, f'Successfully created {created_count} new users.')
            if errors: messages.warning(request, 'Some users could not be created: ' + " ".join(errors))
        except Exception as e: messages.error(request, f"An error occurred: {e}")

    def handle_add_single_user(self, request):
        form = SingleUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.set_password(User.objects.make_random_password())
                user.save()
                # Profile is created by signal, just update it
                user.profile.phone_number = form.cleaned_data.get('phone_number')
                user.profile.reference_image = form.cleaned_data.get('reference_image')
                user.profile.supervisor = request.user
                user.profile.save()
                messages.success(request, f"User '{user.username}' created successfully.")
        else:
            # This part is important for providing feedback on the form
            error_message = ". ".join([f"{field.capitalize()}: {err[0]}" for field, err in form.errors.items()])
            messages.error(request, f"Could not create user. {error_message}")

    def handle_set_time_policy(self, request):
        form = GroupTimePolicyForm(request.POST)
        if form.is_valid():
            form.save(); messages.success(request, f"Time policy for group '{form.cleaned_data['group']}' saved successfully.")
        else:
            for field, error in form.errors.items(): messages.error(request, f"Error in '{field}': {error}")

    def handle_delete_time_policy(self, request):
        if not request.user.is_staff: return
        policy_id = request.POST.get('policy_id')
        if policy_id:
            try:
                policy = GroupTimePolicy.objects.get(id=policy_id)
                group_name = policy.group.name
                policy.delete()
                messages.success(request, f"Time policy for group '{group_name}' has been deleted.")
            except GroupTimePolicy.DoesNotExist:
                messages.error(request, "The policy you tried to delete does not exist.")
        else:
            messages.error(request, "No policy ID provided for deletion.")

# Liveness check view (can be removed if not used)
class LivenessCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        # ... implementation ...
        pass
