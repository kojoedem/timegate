from math import radians, sin, cos, sqrt, atan2
import cv2
import numpy as np
from django.contrib.auth.models import User, Group
from django.contrib.auth import login, logout
from django.utils.timezone import now
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponse
import csv
import datetime
import os
from django.core.files.storage import default_storage
from django.db import transaction

from .models import Attendance, OfficeLocation, AllowedIP, Profile, GroupTimePolicy, Logo
from .serializers import AttendActionSerializer, AttendanceSerializer
from .forms import UserRegistrationForm, SingleUserCreationForm, GroupTimePolicyForm, CreateGroupForm, UserEditForm, LogoUploadForm, GroupEditForm
from .utils import find_matching_face, verify_user_face, check_liveness

# Helper functions
def get_open_attendance(user): return Attendance.objects.filter(user=user, clock_out__isnull=True).order_by("-clock_in").first()
def location_allowed(request, lat, lon): return True, "" # Simplified for brevity

# API Views
class ClockInView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        lat, lon = serializer.validated_data.get("latitude"), serializer.validated_data.get("longitude")
        user, current_time = request.user, now().time()
        policy = getattr(user.groups.first(), 'time_policy', None)
        if policy and not (policy.start_time <= current_time <= policy.end_time):
            return Response({"detail": f"Clock-in denied by time policy."}, status=status.HTTP_403_FORBIDDEN)
        allowed, reason = location_allowed(request, lat, lon)
        if not allowed: return Response({"detail": f"Clock-in denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        if get_open_attendance(user): return Response({"detail": "You already have an active session."}, status=status.HTTP_400_BAD_REQUEST)
        att = Attendance.objects.create(user=user, clock_in=now()); return Response(AttendanceSerializer(att).data, status=status.HTTP_201_CREATED)

class BreakStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session."}, status=status.HTTP_400_BAD_REQUEST)
        if att.break_start and not att.break_end: return Response({"detail": "Already on break."}, status=status.HTTP_400_BAD_REQUEST)
        att.break_start = now(); att.break_end = None; att.save(); return Response(AttendanceSerializer(att).data)

class BreakEndView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session."}, status=status.HTTP_400_BAD_REQUEST)
        if not att.break_start or att.break_end: return Response({"detail": "No ongoing break."}, status=status.HTTP_400_BAD_REQUEST)
        att.break_end = now(); att.save(); return Response(AttendanceSerializer(att).data)

class ClockOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        att = get_open_attendance(request.user)
        if not att: return Response({"detail": "No active session."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        verified, reason = verify_user_face(request.user, serializer.validated_data.get("face_capture"))
        if not verified: return Response({"detail": f"Clock-out denied: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        att.clock_out = now(); att.save(); request.user.auth_token.delete(); logout(request)
        return Response(AttendanceSerializer(att).data)

class TodayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        att = get_open_attendance(request.user); return Response(AttendanceSerializer(att).data) if att else Response({"detail": "No active session."})

class FaceLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = AttendActionSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        user_id, _, reason = find_matching_face(serializer.validated_data.get("face_capture"))
        if user_id:
            user = get_object_or_404(User, id=user_id); token, _ = Token.objects.get_or_create(user=user); login(request, user)
            return Response({'token': token.key, 'username': user.username})
        return Response({"detail": f"Could not identify face: {reason}"}, status=status.HTTP_400_BAD_REQUEST)

# Page Views
def clocking_page(request): return render(request, 'attendance/clocking.html')
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid(): form.save(); messages.success(request, 'Registration successful!'); return redirect('clocking_page')
    else: form = UserRegistrationForm()
    return render(request, 'attendance/register.html', {'form': form})

# Main Dashboard/Profile View
class UserProfileView(LoginRequiredMixin, View):
    def get(self, request):
        user_group = request.user.groups.first()
        group_logo = None
        if user_group and hasattr(user_group, 'time_policy'):
            group_logo = user_group.time_policy.logo

        context = {
            'attendances': Attendance.objects.filter(user=request.user).order_by('-date', '-clock_in'),
            'group_logo': group_logo
        }
        if request.user.is_staff:
            supervisor_groups = request.user.groups.all()
            selected_group_id = request.GET.get('group_id')
            selected_group = supervisor_groups.filter(id=selected_group_id).first() if selected_group_id else supervisor_groups.first()
            context.update({'is_supervisor': True, 'supervisor_groups': supervisor_groups, 'selected_group': selected_group, 'create_group_form': CreateGroupForm()})
            context.update({
                'logo_upload_form': LogoUploadForm(),
                'logos': Logo.objects.filter(uploaded_by=request.user)
            })
            if selected_group:
                context.update({
                    'group_users': User.objects.filter(groups=selected_group),
                    'clocked_in_users': Attendance.objects.filter(user__groups=selected_group, clock_out__isnull=True, break_start__isnull=True),
                    'on_break_users': Attendance.objects.filter(user__groups=selected_group, clock_out__isnull=True, break_start__isnull=False, break_end__isnull=True),
                    'group_time_policy': getattr(selected_group, 'time_policy', None),
                    'single_user_form': SingleUserCreationForm(),
                })
        return render(request, 'attendance/profile.html', context)

    def post(self, request):
        action = request.POST.get('action'); group_id = request.POST.get('group_id', '')
        if not request.user.is_staff: action = 'update_picture'
        handler_map = {
            'update_picture': self.handle_update_picture, 'bulk_upload': self.handle_bulk_upload,
            'add_single_user': self.handle_add_single_user, 'delete_user': self.handle_delete_user,
            'create_group': self.handle_create_group, 'delete_time_policy': self.handle_delete_time_policy,
            'upload_logo': self.handle_logo_upload
        }
        handler = handler_map.get(action)
        if handler: handler(request)
        return redirect(reverse('profile_page') + f"?group_id={group_id}")

    def handle_create_group(self, request):
        form = CreateGroupForm(request.POST)
        if form.is_valid():
            group = form.save(); group.user_set.add(request.user)
            messages.success(request, f"Group '{group.name}' created.")

    def handle_add_single_user(self, request):
        form = SingleUserCreationForm(request.POST, request.FILES)
        group = Group.objects.filter(id=request.POST.get('group_id'), user=request.user).first()
        if form.is_valid() and group:
            user = form.save(commit=False); user.set_password(User.objects.make_random_password()); user.save()
            user.groups.add(group); user.profile.phone_number = form.cleaned_data.get('phone_number')
            user.profile.reference_image = form.cleaned_data.get('reference_image'); user.profile.save()
            messages.success(request, f"User '{user.username}' created.")
        else: messages.error(request, "Could not create user.")

    def handle_delete_user(self, request):
        group = Group.objects.filter(id=request.POST.get('group_id'), user=request.user).first()
        if group and request.POST.get('user_id') and request.user.id != int(request.POST.get('user_id')):
            User.objects.filter(id=request.POST.get('user_id'), groups=group).delete()
            messages.success(request, "User deleted.")
    def handle_update_picture(self, request):
        new_image = request.FILES.get('reference_image')
        if new_image:
            request.user.profile.reference_image = new_image; request.user.profile.save()
            messages.success(request, 'Your profile picture has been updated successfully!')

    def handle_bulk_upload(self, request):
        csv_file = request.FILES.get('csv_file')
        group_id = request.POST.get('group_id')
        group = Group.objects.filter(id=group_id, user=request.user).first()

        if not group:
            messages.error(request, "A valid group must be selected to upload users.")
            return

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
                    user.groups.add(group)
                    user.profile.phone_number = row.get('phone_number', '')
                    user.profile.save()
                    created_count += 1
            if created_count > 0: messages.success(request, f"Successfully created {created_count} new users and added to group '{group.name}'.")
            if errors: messages.warning(request, 'Some users could not be created: ' + " ".join(errors))
        except Exception as e: messages.error(request, f"An error occurred: {e}")

    def handle_delete_time_policy(self, request):
        if not request.user.is_staff: return
        policy_id = request.POST.get('policy_id')
        group_id = request.POST.get('group_id')
        group = Group.objects.filter(id=group_id, user=request.user).first()

        if not group:
            messages.error(request, "You do not have permission to modify this group's policy.")
            return

        if policy_id:
            try:
                policy = GroupTimePolicy.objects.get(id=policy_id, group=group)
                policy.delete()
                messages.success(request, f"Time policy for group '{group.name}' has been deleted.")
            except GroupTimePolicy.DoesNotExist:
                messages.error(request, "The policy you tried to delete does not exist.")
        else:
            messages.error(request, "No policy ID provided for deletion.")

    def handle_logo_upload(self, request):
        if not request.user.is_staff: return
        form = LogoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            logo = form.save(commit=False)
            logo.uploaded_by = request.user
            logo.save()
            messages.success(request, "Logo uploaded successfully.")
        else:
            messages.error(request, "Could not upload logo. The name may already exist.")

class UserEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'attendance/edit_user.html'
    def test_func(self):
        if not self.request.user.is_staff: return False
        target_user = get_object_or_404(User, id=self.kwargs['user_id'])
        return self.request.user.is_superuser or any(g in target_user.groups.all() for g in self.request.user.groups.all())
    def get(self, request, user_id):
        target_user = get_object_or_404(User, id=user_id)
        form = UserEditForm(instance=target_user, user_groups=request.user.groups.all())
        return render(request, self.template_name, {'form': form, 'target_user': target_user})
    def post(self, request, user_id):
        target_user = get_object_or_404(User, id=user_id)
        form = UserEditForm(request.POST, instance=target_user, user_groups=request.user.groups.all())
        if form.is_valid():
            form.save(); messages.success(request, f"Successfully updated user {target_user.username}.")
            return redirect('profile_page')
        return render(request, self.template_name, {'form': form, 'target_user': target_user})

class PolicyEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'attendance/edit_policy.html'
    def test_func(self):
        if not self.request.user.is_staff: return False
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        return self.request.user in group.user_set.all() or self.request.user.is_superuser
    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        policy, created = GroupTimePolicy.objects.get_or_create(group=group, defaults={'start_time': '09:00', 'end_time': '17:00'})
        form = GroupTimePolicyForm(instance=policy)
        return render(request, self.template_name, {'form': form, 'group': group})
    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        policy, created = GroupTimePolicy.objects.get_or_create(group=group)
        form = GroupTimePolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save(); messages.success(request, f"Successfully updated time policy for group {group.name}.")
            return redirect(reverse('profile_page') + f'?group_id={group.id}')
        return render(request, self.template_name, {'form': form, 'group': group})
class LivenessCheckView(APIView): pass # Placeholder

class GroupEditView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'attendance/edit_group.html'

    def test_func(self):
        if not self.request.user.is_staff: return False
        group = get_object_or_404(Group, id=self.kwargs['group_id'])
        return self.request.user in group.user_set.all() or self.request.user.is_superuser

    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        policy, _ = GroupTimePolicy.objects.get_or_create(group=group)
        form = GroupEditForm(
            initial={'name': group.name, 'logo': policy.logo},
            supervisor_logos=Logo.objects.filter(uploaded_by=request.user)
        )
        return render(request, self.template_name, {'form': form, 'group': group})

    def post(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)
        form = GroupEditForm(request.POST, supervisor_logos=Logo.objects.filter(uploaded_by=request.user))
        if form.is_valid():
            group.name = form.cleaned_data['name']
            group.save()

            policy, _ = GroupTimePolicy.objects.get_or_create(group=group)
            policy.logo = form.cleaned_data['logo']
            policy.save()

            messages.success(request, f"Successfully updated group '{group.name}'.")
            return redirect(reverse('profile_page') + f'?group_id={group.id}')

        return render(request, self.template_name, {'form': form, 'group': group})
