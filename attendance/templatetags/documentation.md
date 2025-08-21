Of course. Here is a detailed documentation of the TimeGate project, including its current capabilities, the technologies used, and the features and fixes that have been implemented.

Project Documentation: TimeGate Smart Clocking System
1. Project Overview
TimeGate is a modern, web-based employee attendance system designed for security and ease of use. It leverages facial recognition for authentication and provides a suite of tools for users, supervisors, and administrators to manage time and attendance effectively. The system is built to be responsive, working across devices from mobile phones to desktops.

2. Core Technologies Used
Backend:
Framework: Django 5.0.6
API: Django Rest Framework (for token-based authentication)
Computer Vision: OpenCV (opencv-python-contrib) for facial recognition.
Database: SQLite (default development database).
Frontend:
Structure: HTML5, CSS3, Plain JavaScript (ES6+).
Styling & Responsiveness: Bootstrap 5.
APIs: Browser localStorage for session persistence, navigator.mediaDevices.getUserMedia for camera access, navigator.geolocation for location services.
3. Current Features & Functionality
The application now has a complete workflow for user registration, authentication, time tracking, and administration.

a) User Registration & Profile Management

Individual Registration (/register/): A public registration page where a new user can sign up with their username, full name, phone number, and a reference face image for facial recognition.
Face Uniqueness Check: The system prevents the same person from registering multiple accounts by comparing the new user's face against all existing reference images.
User Profile Page (/profile/): Once logged in, a user can access their profile page to:
View their personal details.
See their current reference photo.
Upload a new reference photo to update their facial recognition data.
View a complete history of their attendance records (date, clock-in/out times, total hours).
b) Authentication & Clocking

Automatic Facial Login: The main page (/) uses the device's webcam to automatically recognize a registered user and log them in. This creates both an API token (for API calls) and a Django session (for accessing web pages).
State Persistence: The user's login session is remembered even if the browser is refreshed. The camera will not re-open, and the clock-in timer will continue to run correctly.
Clocking Actions: Logged-in users can perform standard clocking actions:
Clock In / Clock Out
Start Break / End Break
Secure Clock-Out: Clocking out requires a final facial verification to ensure the correct user is ending the session. Upon successful clock-out, the user's session is completely terminated (both token and session cookie are destroyed), and the page is reloaded.
Geolocation Enforcement: Clock-in and clock-out actions require the user's browser to provide geolocation data.
c) Supervisor & Administrator Features

Supervisor Role: Users can be designated as supervisors for other users. This is managed in the Django admin panel.
Admin Dashboard (/admin-dashboard/): A page accessible only to staff/supervisors that provides:
Real-time statistics: Total users, number of users clocked in, and number of users on break.
Live lists of which users are currently clocked in or on break.
Scoped View: The dashboard is filtered. Superusers see all data, while supervisors only see data for the users they directly manage.
CSV Attendance Reporting: Admins and supervisors can download a CSV report of attendance records for a specified date range. The report is filtered for supervisors.
Bulk User Registration: On the admin dashboard, a supervisor can upload a CSV file (with columns: username, first_name, last_name, phone_number) to create multiple user accounts at once. The new users are automatically assigned to the uploading supervisor. They will then need to log in and upload their own reference photos.
Group-Based Time Policies: Admins can create user groups and assign a specific time window (e.g., 9:00 AM - 5:00 PM) to each group. Users in a group are only allowed to clock in during their designated time.
4. Major Bug Fixes & Enhancements
State Persistence: Fixed critical bugs where the login state and timer were lost on page refresh by using localStorage.
Profile Page Access: Fixed a 404 error that prevented users from accessing their profile page after a facial login by creating a Django session.
Admin User Creation: Fixed a critical IntegrityError that occurred when creating users in the Django admin.
UI/UX Overhaul:
The entire application was redesigned with Bootstrap 5 for a clean, modern, and responsive interface.
Raw API responses are no longer shown to the user. Instead, a user-friendly notification system provides clear feedback for all actions.
Logout Security: The logout process was enhanced to clear browser cache via HTTP headers and force a page reload for better security.
5. How to Use (Developer Quickstart)
Install Dependencies:
pip install -r requirements.txt
Apply Migrations:
python manage.py migrate
Create an Admin/Superuser:
python manage.py createsuperuser
Run the Development Server:
python manage.py runserver
Using the App:
Navigate to http://127.0.0.1:8000/register/ to create a user with a clear face photo.
Or, log in as an admin, create a group, assign a time policy, create a supervisor, and then use the supervisor to bulk-upload users.
Go to the main page (http://127.0.0.1:8000/) to test the facial login.