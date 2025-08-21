import datetime
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.core.files.uploadedfile import SimpleUploadedFile
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
        mock_verify_face.return_value = (True, "Face verified.")
        Attendance.objects.create(user=self.user, clock_in=now())
        dummy_face_capture = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        data = {'latitude': 5.6037, 'longitude': -0.1870, 'face_capture': dummy_face_capture}
        response = self.client.post('/api/clock-out/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.get().clock_out)
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

    def test_admin_dashboard_csv_export(self):
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='testuser', password='testpassword')
        clock_in_time = now()
        clock_out_time = clock_in_time + datetime.timedelta(hours=8)
        Attendance.objects.create(user=self.user, clock_in=clock_in_time, clock_out=clock_out_time, total_seconds=8*3600, date=clock_in_time.date())
        start_date = now().date()
        end_date = now().date()
        response = self.client.post('/admin-dashboard/', {'start_date': start_date.strftime('%Y-%m-%d'),'end_date': end_date.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        content = response.content.decode('utf-8')
        self.assertIn('User,Date,Clock In,Clock Out,Total Hours', content)
        self.assertIn(self.user.username, content)
        self.assertIn('8.0', content)

    @patch('attendance.forms.find_matching_face')
    def test_registration_duplicate_face(self, mock_find_face):
        mock_find_face.return_value = (1, 0.5, "Match found.")
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDAT\x08\xd7c`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'
        dummy_image = SimpleUploadedFile("face.png", png_data, content_type="image/png")
        data = {'username': 'newuser','password': 'newpassword','first_name': 'New','last_name': 'User','phone_number': '1234567890','reference_image': dummy_image}
        response = self.client.post('/register/', data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This face appears to be already registered to another user.")
        self.assertEqual(User.objects.count(), 1)
        mock_find_face.return_value = (None, None, "No match found.")
        dummy_image_2 = SimpleUploadedFile("face2.png", png_data, content_type="image/png")
        data['reference_image'] = dummy_image_2
        response = self.client.post('/register/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 2)

    @patch('attendance.views.check_liveness')
    def test_liveness_check_view(self, mock_check_liveness):
        mock_check_liveness.return_value = True
        dummy_video = SimpleUploadedFile("video.webm", b"video_content", content_type="video/webm")
        self.client.credentials()
        response = self.client.post('/api/liveness-check/', {'video_clip': dummy_video})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], "Liveness check passed.")
        mock_check_liveness.return_value = False
        dummy_video_2 = SimpleUploadedFile("video2.webm", b"video_content_2", content_type="video/webm")
        response = self.client.post('/api/liveness-check/', {'video_clip': dummy_video_2})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], "Liveness check failed.")
