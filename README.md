# TimeGate ⏳🔐  

TimeGate is a **secure identity verification and attendance tracking system** that leverages **facial recognition, geolocation, and API integrations** to provide seamless authentication.  

## 🚀 Features  
- **Face Verification:** Users clock in/out or log in by scanning their face with the device camera.  
- **Geo-fencing:** Login and Wi-Fi access restricted within a defined GPS radius for extra security.  
- **Clocking System:**  
  - Automatic clock-in when face verification succeeds  
  - Clock-out and break management (requires camera verification again to prevent impersonation)  
- **Wi-Fi Hotspot Authentication (MikroTik API Integration):**  
  - First implementation connects TimeGate with MikroTik Hotspot for Wi-Fi authorization  
  - Users must verify with camera before gaining access to Wi-Fi  
- **Public API Ready:** Can be extended to verify users across multiple services (remote work apps, office systems, etc.)  

## 🛠️ Tech Stack  
- **Frontend:** Web app with camera access  
- **Backend:** Python / FastAPI (planned)  
- **Database:** PostgreSQL / SQLite (for initial testing)  
- **Networking:** MikroTik API integration for hotspot verification  

## 📌 Use Cases  
- Employee attendance tracking  
- Remote worker verification  
- Public Wi-Fi authentication  
- Event access control  

## 🌍 Vision  
TimeGate aims to become a **universal web-based verification platform** that organizations and developers can plug into their systems for secure, location-aware, camera-based authentication.  

## 📦 Installation (Development)  
```bash
# Clone repository
git clone https://github.com/kojoedem/timegate.git
cd timegate

# Install dependencies (example if using Python/FastAPI)
pip install -r requirements.txt

# Run app
uvicorn main:app --reload
```

## 🗺️ Roadmap  
- [x] Clocking system with camera verification  
- [ ] Geo-fencing support  
- [ ] MikroTik Wi-Fi authentication  
- [ ] Public API release  
- [ ] Dashboard for admins  

## 📄 License  
MIT License – free to use and modify.  
