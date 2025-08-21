document.addEventListener("DOMContentLoaded", () => {
    // Global variables
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const apiUrl = "/api/";
    let clockInTime = null;
    let timerInterval = null;
    let authToken = null;
    let faceLoginInterval = null;
    let cameraStream = null;

    // === UTILITY FUNCTIONS ===

    function showNotification(message, type = 'info') {
        const notificationArea = document.getElementById('notification-area');
        const alertClass = `alert alert-${type} alert-dismissible fade show`;
        notificationArea.innerHTML = `
            <div class="${alertClass}" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
    }

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }
    }

    function startCamera() {
        return new Promise((resolve, reject) => {
            if (navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(stream => {
                        cameraStream = stream;
                        video.srcObject = stream;
                        video.style.display = 'block';
                        resolve(stream);
                    }).catch(error => {
                        showNotification("Could not access camera. Please grant permission.", "danger");
                        reject(error);
                    });
            } else {
                showNotification("Camera not supported.", "danger");
                reject(new Error("getUserMedia not supported"));
            }
        });
    }

    function captureImage() {
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, 320, 240);
        return canvas.toDataURL('image/png');
    }

    function startClockTimer() {
        if (!clockInTime) return;
        clearInterval(timerInterval);
        function updateElapsedTime() {
            if (!clockInTime) return;
            const now = new Date();
            const elapsedMilliseconds = now - clockInTime;
            const hours = Math.floor(elapsedMilliseconds / 3600000);
            const minutes = Math.floor((elapsedMilliseconds % 3600000) / 60000);
            const seconds = Math.floor((elapsedMilliseconds % 60000) / 1000);
            document.getElementById("elapsed-time").innerText = `${hours}h ${minutes}m ${seconds}s`;
        }
        updateElapsedTime();
        timerInterval = setInterval(updateElapsedTime, 1000);
    }

    // === UI UPDATE FUNCTIONS ===

    function showLoggedInState(username) {
        document.getElementById('camera-container').style.display = 'none';
        document.getElementById('confirm-clockout-container').style.display = 'none';
        document.getElementById('clocking-controls').style.display = 'block';
        document.getElementById('nav-links').style.display = 'inline';
        document.getElementById('user-greeting').innerHTML = `Welcome, <span class="fw-bold text-primary">${username}</span>!`;
    }

    function showLoggedOutState() {
        document.getElementById('camera-container').style.display = 'block';
        document.getElementById('clocking-controls').style.display = 'none';
        document.getElementById('nav-links').style.display = 'none';
        document.getElementById('confirm-clockout-container').style.display = 'none';
        document.getElementById('user-greeting').innerText = 'Please look at the camera to log in...';
        showNotification("Please look at the camera to log in.", "info");
        startCamera().then(() => {
            faceLoginInterval = setInterval(attemptFaceLogin, 2500);
        });
    }

    // === API & STATE LOGIC ===

    async function makeRequest(endpoint, body = {}) {
        if (!authToken) {
            showNotification("Authentication failed. Please refresh.", "danger");
            return Promise.reject("No auth token");
        }
        try {
            const response = await fetch(`${apiUrl}${endpoint}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Token ${authToken}` },
                body: JSON.stringify(body)
            });
            const data = await response.json();
            if (response.ok) {
                showNotification(`${endpoint.replace('-', ' ')} successful!`, 'success');
                if (endpoint === "clock-in") {
                    clockInTime = new Date(data.clock_in);
                    localStorage.setItem('clockInTime', clockInTime);
                    startClockTimer();
                } else if (endpoint === "clock-out") {
                    clockInTime = null;
                    localStorage.removeItem('clockInTime');
                    clearInterval(timerInterval);
                    document.getElementById("elapsed-time").innerText = "Not clocked in yet.";
                }
                return data;
            } else {
                const errorMessage = data.detail || 'An unknown error occurred.';
                showNotification(`Error: ${errorMessage}`, 'danger');
                return Promise.reject(data);
            }
        } catch (error) {
            showNotification("Network Error: Could not connect to the server.", 'danger');
            return Promise.reject(error);
        }
    }

    async function attemptFaceLogin() {
        if (!cameraStream) return;
        const imageData = captureImage();
        try {
            const response = await fetch(`${apiUrl}face-login/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({face_capture: imageData})
            });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('authToken', data.token);
                localStorage.setItem('username', data.username);
                clearInterval(faceLoginInterval);
                stopCamera();
                restoreState(); // Re-run state logic to update UI
            }
        } catch (error) {}
    }

    async function fetchCurrentStatus() {
        if (!authToken) return;
        try {
            const response = await fetch(`${apiUrl}today/`, {
                headers: { "Authorization": `Token ${authToken}` }
            });
            if(response.ok) {
                const data = await response.json();
                if (data.clock_in && !data.clock_out) {
                    clockInTime = new Date(data.clock_in);
                    localStorage.setItem('clockInTime', clockInTime);
                    startClockTimer();
                }
            }
        } catch(error) {
            console.error("Could not fetch today's status", error);
        }
    }

    function restoreState() {
        authToken = localStorage.getItem('authToken');
        const username = localStorage.getItem('username');
        const storedClockInTime = localStorage.getItem('clockInTime');

        if (authToken && username) {
            showLoggedInState(username);
            if (storedClockInTime) {
                clockInTime = new Date(storedClockInTime);
                startClockTimer();
            } else {
                fetchCurrentStatus();
            }
        } else {
            showLoggedOutState();
        }
    }

    // === EVENT HANDLERS ===
    window.clockIn = function() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                makeRequest("clock-in", { latitude: pos.coords.latitude, longitude: pos.coords.longitude });
            }, err => showNotification("Geolocation is required.", "warning"));
        } else { showNotification("Geolocation is not supported.", "warning"); }
    }
    window.startBreak = function() { makeRequest("break-start"); }
    window.endBreak = function() { makeRequest("break-end"); }
    window.initiateClockOut = function() {
        document.getElementById('clocking-controls').style.display = 'none';
        document.getElementById('camera-container').style.display = 'block';
        document.getElementById('confirm-clockout-container').style.display = 'block';
        showNotification("Please look at the camera to verify for clock-out.", "info");
        startCamera();
    }
    window.confirmClockOut = function() {
        const imageData = captureImage();
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                makeRequest("clock-out", { latitude: pos.coords.latitude, longitude: pos.coords.longitude, face_capture: imageData })
                .then(() => {
                    localStorage.removeItem('authToken');
                    localStorage.removeItem('username');
                    localStorage.removeItem('clockInTime');
                    authToken = null;
                    stopCamera();
                    showLoggedOutState();
                }).catch(err => {
                    showNotification("Clock-out failed. Please try again.", "danger");
                    document.getElementById('clocking-controls').style.display = 'block';
                    document.getElementById('camera-container').style.display = 'none';
                    document.getElementById('confirm-clockout-container').style.display = 'none';
                    stopCamera();
                });
            }, err => showNotification("Geolocation is required.", "warning"));
        } else { showNotification("Geolocation is not supported.", "warning"); }
    }

    // Initial load
    restoreState();
});
