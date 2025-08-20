from django.contrib.auth.models import User
from django.utils.timezone import now
from unittest.mock import patch
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from rest_framework import status
from .models import OfficeLocation, Attendance

class AttendanceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.office = OfficeLocation.objects.create(
            name="Test Office",
            latitude=5.6037,
            longitude=-0.1870,
            allowed_radius=1000
        )

    def test_clock_in_success(self):
        data = {'latitude': 5.6037, 'longitude': -0.1870}
        response = self.client.post('/api/clock-in/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.count(), 1)
        self.assertEqual(Attendance.objects.get().user, self.user)

    def test_clock_in_already_clocked_in(self):
        Attendance.objects.create(user=self.user, clock_in=now())
        data = {'latitude': 5.6037, 'longitude': -0.1870}
        response = self.client.post('/api/clock-in/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_break_start_success(self):
        Attendance.objects.create(user=self.user, clock_in=now())
        response = self.client.post('/api/break-start/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.get().break_start)

    def test_break_start_not_clocked_in(self):
        response = self.client.post('/api/break-start/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_break_end_success(self):
        att = Attendance.objects.create(user=self.user, clock_in=now(), break_start=now())
        response = self.client.post('/api/break-end/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.get().break_end)

    def test_break_end_not_on_break(self):
        Attendance.objects.create(user=self.user, clock_in=now())
        response = self.client.post('/api/break-end/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('attendance.views.verify_user_face')
    def test_clock_out_success(self, mock_verify_face):
        # Configure the mock to simulate successful face verification
        mock_verify_face.return_value = (True, "Face verified.")

        Attendance.objects.create(user=self.user, clock_in=now())

        # We need to send a dummy face capture to pass the serializer
        dummy_face_capture = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        data = {
            'latitude': 5.6037,
            'longitude': -0.1870,
            'face_capture': dummy_face_capture
        }

        response = self.client.post('/api/clock-out/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.get().clock_out)

        # Check that the token was deleted
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_clock_out_not_clocked_in(self):
        data = {'latitude': 5.6037, 'longitude': -0.1870}
        response = self.client.post('/api/clock-out/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_today_status_view(self):
        Attendance.objects.create(user=self.user, clock_in=now())
        response = self.client.get('/api/today/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user'], self.user.id)
