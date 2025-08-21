document.addEventListener("DOMContentLoaded", () => {
    // Global variables
    const video = document.getElementById('video'); // Assumes a video element exists on the page for clock-out
    const canvas = document.getElementById('canvas'); // Assumes a canvas element exists
    const apiUrl = "/api/";
    let clockInTime = null;
    let timerInterval = null;
    let authToken = localStorage.getItem('authToken'); // Get token from storage
    let cameraStream = null;

    // === UTILITY FUNCTIONS ===

    function showNotification(message, type = 'info') {
        const notificationArea = document.getElementById('notification-area');
        if (!notificationArea) return;
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
        const cameraContainer = document.getElementById('camera-container-profile');
        if(cameraContainer) cameraContainer.style.display = 'none';
    }

    function startCamera() {
        return new Promise((resolve, reject) => {
            if (navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(stream => {
                        cameraStream = stream;
                        if(video) {
                            video.srcObject = stream;
                            video.style.display = 'block';
                        }
                        const cameraContainer = document.getElementById('camera-container-profile');
                        if(cameraContainer) cameraContainer.style.display = 'block';
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
        if (!video || !canvas) return null;
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, 320, 240);
        return canvas.toDataURL('image/png');
    }

    function startClockTimer() {
        if (!clockInTime) return;
        const elapsedTimeEl = document.getElementById("elapsed-time");
        if (!elapsedTimeEl) return;

        clearInterval(timerInterval);
        function updateElapsedTime() {
            if (!clockInTime) return;
            const now = new Date();
            const elapsedMilliseconds = now - clockInTime;
            const hours = Math.floor(elapsedMilliseconds / 3600000);
            const minutes = Math.floor((elapsedMilliseconds % 3600000) / 60000);
            const seconds = Math.floor((elapsedMilliseconds % 60000) / 1000);
            elapsedTimeEl.innerText = `${hours}h ${minutes}m ${seconds}s`;
        }
        updateElapsedTime();
        timerInterval = setInterval(updateElapsedTime, 1000);
    }

    // === API & STATE LOGIC ===

    async function makeRequest(endpoint, body = {}) {
        if (!authToken) {
            showNotification("Authentication failed. Please log in again.", "danger");
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
                showNotification(`${endpoint.replace(/-/g, ' ')} successful!`, 'success');
                if (endpoint === "clock-in") {
                    clockInTime = new Date(data.clock_in);
                    localStorage.setItem('clockInTime', clockInTime);
                    startClockTimer();
                    document.getElementById('clocking-dashboard').style.display = 'block';
                    document.getElementById('confirm-clockout-container').style.display = 'none';
                } else if (endpoint === "clock-out") {
                    clockInTime = null;
                    localStorage.removeItem('clockInTime');
                    clearInterval(timerInterval);
                    const elapsedTimeEl = document.getElementById("elapsed-time");
                    if (elapsedTimeEl) elapsedTimeEl.innerText = "Not clocked in yet.";
                    // On successful clock-out, we might want to refresh or update UI
                    location.reload();
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
            } else if (response.status === 401) {
                // If token is invalid, redirect to login
                localStorage.clear();
                window.location.href = '/';
            }
        } catch(error) {
            console.error("Could not fetch today's status", error);
        }
    }

    function restoreState() {
        if (!authToken) {
            // If there's no token, redirect to the login page.
            window.location.href = '/';
            return;
        }

        const storedClockInTime = localStorage.getItem('clockInTime');
        if (storedClockInTime) {
            clockInTime = new Date(storedClockInTime);
            startClockTimer();
        } else {
            // Fetch status from server to see if we are clocked in from another session
            fetchCurrentStatus();
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
        document.getElementById('clocking-dashboard').style.display = 'none';
        document.getElementById('confirm-clockout-container').style.display = 'block';
        startCamera();
    }
    window.confirmClockOut = function() {
        const imageData = captureImage();
        if (!imageData) {
            showNotification("Could not capture image for verification.", "danger");
            return;
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                makeRequest("clock-out", { latitude: pos.coords.latitude, longitude: pos.coords.longitude, face_capture: imageData })
                .catch(err => {
                    showNotification("Clock-out failed. Please try again.", "danger");
                    // Show controls again on failure
                    document.getElementById('clocking-dashboard').style.display = 'block';
                    document.getElementById('confirm-clockout-container').style.display = 'none';
                    stopCamera();
                });
            }, err => showNotification("Geolocation is required for clock-out.", "warning"));
        } else { showNotification("Geolocation is not supported.", "warning"); }
    }
    window.cancelClockOut = function() {
        document.getElementById('clocking-dashboard').style.display = 'block';
        document.getElementById('confirm-clockout-container').style.display = 'none';
        stopCamera();
    }


    // Initial load
    restoreState();
});
