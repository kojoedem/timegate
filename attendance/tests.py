import datetime
from django.contrib.auth.models import User, Group
from django.utils.timezone import now
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from rest_framework import status
from .models import OfficeLocation, Attendance, GroupTimePolicy

class AttendanceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.office = OfficeLocation.objects.create(latitude=5.6037, longitude=-0.1870, allowed_radius=1000)

    # ... (existing API tests are fine, no changes needed here) ...
    def test_clock_in_success(self):
        data = {'latitude': 5.6037, 'longitude': -0.1870}
        response = self.client.post('/api/clock-in/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class UserProfileViewTests(APITestCase):
    def setUp(self):
        self.supervisor = User.objects.create_user(username='supervisor', password='password', is_staff=True)
        self.user_a = User.objects.create_user(username='user_a', password='password')
        self.user_b = User.objects.create_user(username='user_b', password='password')

        self.user_a.profile.supervisor = self.supervisor
        self.user_a.profile.save()

        self.client = APIClient()
        self.client.login(username='supervisor', password='password')

    def test_supervisor_view_context(self):
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_supervisor'])
        self.assertIn('single_user_form', response.context)
        self.assertIn('time_policy_form', response.context)
        # Supervisor should only see users they supervise
        self.assertIn(self.user_a, response.context['supervised_users'])
        self.assertNotIn(self.user_b, response.context['supervised_users'])

    def test_regular_user_view_context(self):
        self.client.login(username='user_a', password='password')
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('is_supervisor', response.context)

    def test_supervisor_can_add_single_user(self):
        user_count = User.objects.count()
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDAT\x08\xd7c`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'
        dummy_image = SimpleUploadedFile("face.png", png_data, content_type="image/png")
        data = {
            'action': 'add_single_user',
            'username': 'new_user_from_form',
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '12345',
            'reference_image': dummy_image,
        }
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 302) # Redirects on success
        self.assertEqual(User.objects.count(), user_count + 1)
        new_user = User.objects.get(username='new_user_from_form')
        self.assertEqual(new_user.profile.supervisor, self.supervisor)

    def test_supervisor_can_manage_time_policies(self):
        group = Group.objects.create(name='Test Group')
        policy_count = GroupTimePolicy.objects.count()

        # Create a policy
        create_data = {
            'action': 'set_time_policy',
            'group': group.id,
            'start_time': '09:00',
            'end_time': '17:00'
        }
        response = self.client.post(reverse('profile_page'), create_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupTimePolicy.objects.count(), policy_count + 1)

        # Delete the policy
        policy_id = GroupTimePolicy.objects.first().id
        delete_data = {
            'action': 'delete_time_policy',
            'policy_id': policy_id
        }
        response = self.client.post(reverse('profile_page'), delete_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GroupTimePolicy.objects.count(), policy_count)

    def test_supervisor_can_download_csv(self):
        start_date = now().date()
        end_date = now().date()
        data = {
            'action': 'download_csv',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        }
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_supervisor_can_bulk_upload(self):
        user_count = User.objects.count()
        csv_content = "username,first_name,last_name,phone_number\ncsvuser1,fn1,ln1,111\ncsvuser2,fn2,ln2,222"
        csv_file = SimpleUploadedFile("users.csv", csv_content.encode('utf-8'), content_type="text/csv")
        data = {
            'action': 'bulk_upload',
            'csv_file': csv_file,
        }
        response = self.client.post(reverse('profile_page'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), user_count + 2)
        new_user = User.objects.get(username='csvuser1')
        self.assertEqual(new_user.profile.supervisor, self.supervisor)
