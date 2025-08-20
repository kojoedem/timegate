const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const apiUrl = "/api/";
let clockInTime = null;
let timerInterval = null;
let authToken = null;
let faceLoginInterval = null;
let cameraStream = null;

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
                .then(function (stream) {
                    cameraStream = stream;
                    video.srcObject = stream;
                    video.style.display = 'block';
                    resolve(stream);
                })
                .catch(function (error) {
                    showNotification("Could not access the camera. Please ensure it is enabled and permissions are granted.", "danger");
                    reject(error);
                });
        } else {
            showNotification("Camera functionality is not supported by this browser.", "danger");
            reject(new Error("getUserMedia not supported"));
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    showNotification("Please look at the camera to log in.", "info");
    startCamera().then(() => {
        faceLoginInterval = setInterval(attemptFaceLogin, 2500);
    }).catch(() => {
        document.getElementById('user-greeting').innerText = 'Camera access is required for this application.';
    });
});

function captureImage() {
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, 320, 240);
    return canvas.toDataURL('image/png');
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
            authToken = data.token;
            clearInterval(faceLoginInterval);
            stopCamera();
            document.getElementById('camera-container').style.display = 'none';
            document.getElementById('clocking-controls').style.display = 'block';
            document.getElementById('user-greeting').innerHTML = `Welcome, <span class="fw-bold text-primary">${data.username}</span>!`;
            showNotification('Logged in successfully!', 'success');
        }
    } catch (error) {}
}

async function makeRequest(endpoint, body = {}) {
    if (!authToken) {
        showNotification("Authentication failed. Please refresh and log in again.", "danger");
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
                startClockTimer();
            } else if (endpoint === "clock-out") {
                clockInTime = null;
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

function clockIn() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(pos) {
            makeRequest("clock-in", { latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        }, function(err) { showNotification("Geolocation is required to clock in.", "warning"); });
    } else { showNotification("Geolocation is not supported by this browser.", "warning"); }
}

function startBreak() { makeRequest("break-start"); }
function endBreak() { makeRequest("break-end"); }

function initiateClockOut() {
    document.getElementById('clocking-controls').style.display = 'none';
    document.getElementById('camera-container').style.display = 'block';
    document.getElementById('confirm-clockout-container').style.display = 'block';
    showNotification("Please look at the camera to verify for clock-out.", "info");
    startCamera();
}

function confirmClockOut() {
    const imageData = captureImage();
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(pos) {
            makeRequest("clock-out", { latitude: pos.coords.latitude, longitude: pos.coords.longitude, face_capture: imageData })
            .then(() => {
                authToken = null;
                stopCamera();
                showNotification("You have been successfully clocked out.", "success");
                document.getElementById('user-greeting').innerText = 'You have been logged out. Refresh to log in again.';
                document.getElementById('confirm-clockout-container').style.display = 'none';
                document.getElementById('camera-container').style.display = 'none';
            }).catch(err => {
                // The error is already shown by makeRequest
                // Reset UI for another attempt
                document.getElementById('clocking-controls').style.display = 'block';
                document.getElementById('camera-container').style.display = 'none';
                document.getElementById('confirm-clockout-container').style.display = 'none';
                stopCamera();
            });
        }, function(err) { showNotification("Geolocation is required to clock out.", "warning"); });
    } else { showNotification("Geolocation is not supported by this browser.", "warning"); }
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
