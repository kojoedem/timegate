
# TimeGate – Open-source Location-restricted Clocking (Django + DRF)

This is a **starter code** for your universal clocking system. It supports:
- Clock In / Break Start / Break End / Clock Out
- Geofencing via GPS (lat/lon) and/or Office IP whitelist
- Token-based auth
- Simple, SQLite by default

## Quickstart

```bash
# 1) Create and activate a virtualenv (recommended)
python3 -m venv .venv && source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Setup Django
python manage.py migrate
python manage.py createsuperuser

# 4) Get an API token
# Log into Django admin at http://127.0.0.1:8000/admin and create a token for your user
# (or use DRF authtoken endpoint if you add it later)

# 5) Run server
python manage.py runserver

# 6) Create an Office Location in admin
# - name, latitude, longitude, allowed_radius (e.g., 50 meters)
# Optionally add AllowedIP entries

# Example requests (use your token)
curl -X POST http://127.0.0.1:8000/api/clock-in/   -H "Authorization: Token YOUR_TOKEN"   -H "Content-Type: application/json"   -d '{"latitude": 5.6037, "longitude": -0.1870}'

curl -X POST http://127.0.0.1:8000/api/break-start/ -H "Authorization: Token YOUR_TOKEN"
curl -X POST http://127.0.0.1:8000/api/break-end/   -H "Authorization: Token YOUR_TOKEN"
curl -X POST http://127.0.0.1:8000/api/clock-out/   -H "Authorization: Token YOUR_TOKEN"
```

## Moving to FastAPI later
You can keep the same database schema and build a FastAPI service that reads/writes the `attendance` tables.
