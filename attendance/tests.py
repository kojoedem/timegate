import datetime
from django.contrib.auth.models import User, Group
from django.utils.timezone import now
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from rest_framework import status
from .models import OfficeLocation, Attendance, GroupTimePolicy, Logo

class AttendanceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.office = OfficeLocation.objects.create(latitude=5.6037, longitude=-0.1870, allowed_radius=1000)

    def test_clock_in_success(self):
        data = {'latitude': 5.6037, 'longitude': -0.1870}
        response = self.client.post('/api/clock-in/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class UserProfileViewTests(APITestCase):
    def setUp(self):
        self.supervisor = User.objects.create_user(username='supervisor', password='password', is_staff=True)
        self.user_a = User.objects.create_user(username='user_a', password='password')
        self.user_b = User.objects.create_user(username='user_b', password='password')

        # Create a default group for the supervisor
        self.group1 = Group.objects.create(name='Group One')
        self.supervisor.groups.add(self.group1)

    def test_supervisor_view_context(self):
        self.client.login(username='supervisor', password='password')
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_supervisor'])
        self.assertEqual(response.context['selected_group'], self.group1)

    def test_supervisor_can_create_group(self):
        self.client.login(username='supervisor', password='password')
        group_count = Group.objects.count()
        response = self.client.post(reverse('profile_page'), {'action': 'create_group', 'name': 'New Test Group', 'group_id': self.group1.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Group.objects.count(), group_count + 1)
        new_group = Group.objects.get(name='New Test Group')
        self.assertIn(self.supervisor, new_group.user_set.all())

    def test_supervisor_can_delete_user(self):
        self.client.login(username='supervisor', password='password')
        user_to_delete = User.objects.create_user(username='deleteme', password='password')
        user_to_delete.groups.add(self.group1)

        user_count = User.objects.count()
        data = {'action': 'delete_user', 'user_id': user_to_delete.id, 'group_id': self.group1.id}
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), user_count - 1)

    def test_supervisor_can_edit_user(self):
        self.client.login(username='supervisor', password='password')
        self.user_a.groups.add(self.group1)
        group2 = Group.objects.create(name='Group Two')
        self.supervisor.groups.add(group2)

        data = {'first_name': 'Updated', 'last_name': 'Name', 'email': 'u@test.com', 'phone_number': '111', 'groups': [group2.id]}
        response = self.client.post(reverse('edit_user', kwargs={'user_id': self.user_a.id}), data)
        self.assertEqual(response.status_code, 302)

        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.first_name, 'Updated')
        self.assertIn(group2, self.user_a.groups.all())

    def test_supervisor_can_edit_policy(self):
        self.client.login(username='supervisor', password='password')
        policy = GroupTimePolicy.objects.create(group=self.group1, start_time='09:00', end_time='17:00')

        data = {'start_time': '10:00', 'end_time': '18:00', 'group': self.group1.id}
        response = self.client.post(reverse('edit_policy', kwargs={'group_id': self.group1.id}), data)
        self.assertEqual(response.status_code, 302)

        policy.refresh_from_db()
        self.assertEqual(policy.start_time, datetime.time(10, 0))

    def test_supervisor_can_bulk_upload(self):
        self.client.login(username='supervisor', password='password')
        user_count = User.objects.count()
        csv_content = "username,first_name,last_name,phone_number\ncsvuser1,fn1,ln1,111"
        csv_file = SimpleUploadedFile("users.csv", csv_content.encode('utf-8'), content_type="text/csv")
        data = {'action': 'bulk_upload', 'csv_file': csv_file, 'group_id': self.group1.id}
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), user_count + 1)
        new_user = User.objects.get(username='csvuser1')
        self.assertIn(self.group1, new_user.groups.all())

    def test_supervisor_can_upload_logo(self):
        self.client.login(username='supervisor', password='password')
        logo_count = Logo.objects.count()
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDAT\x08\xd7c`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'
        dummy_image = SimpleUploadedFile("logo.png", png_data, content_type="image/png")
        data = {'action': 'upload_logo', 'name': 'Test Logo', 'image': dummy_image, 'group_id': self.group1.id}
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Logo.objects.count(), logo_count + 1)
        new_logo = Logo.objects.get(name='Test Logo')
        self.assertEqual(new_logo.uploaded_by, self.supervisor)

    def test_supervisor_can_assign_logo_to_group(self):
        self.client.login(username='supervisor', password='password')
        logo = Logo.objects.create(name='My Test Logo', uploaded_by=self.supervisor)
        data = {'name': 'New Group Name', 'logo': logo.id}
        response = self.client.post(reverse('edit_group', kwargs={'group_id': self.group1.id}), data)
        self.assertEqual(response.status_code, 302)
        self.group1.refresh_from_db()
        self.assertEqual(self.group1.time_policy.logo, logo)

    def test_user_sees_group_logo(self):
        dummy_image = SimpleUploadedFile("logo.png", b"file_content", content_type="image/png")
        logo = Logo.objects.create(name='User Logo', uploaded_by=self.supervisor, image=dummy_image)
        policy = GroupTimePolicy.objects.create(group=self.group1, start_time='09:00', end_time='17:00', logo=logo)
        self.user_a.groups.add(self.group1)

        self.client.login(username='user_a', password='password')
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('group_logo', response.context)
        self.assertEqual(response.context['group_logo'], logo)
